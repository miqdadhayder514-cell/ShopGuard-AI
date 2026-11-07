import time
from typing import Any, List, Optional, Tuple
import cv2
import numpy as np

from ..detection.person_detector import Detection
from ..intrusion.zone_manager import Zone
from ..intrusion.intrusion_detector import IntrusionEvent
from ..security.security_controller import SecurityState


class FeedVisualizer:
    """
    Renders professional monitoring overlays on top of camera frames for live operator viewing.
    Renders detection boxes, track IDs, zones, security state banners, and incident alerts.
    """

    COLOR_MAP = {
        SecurityState.DISARMED: (160, 160, 160),    # Slate Gray
        SecurityState.ARMING: (0, 215, 255),        # Gold / Amber
        SecurityState.ARMED: (0, 200, 0),           # Bright Green
        SecurityState.PARTIAL: (0, 140, 255),       # Orange
        SecurityState.OFFLINE: (0, 0, 220),         # Crimson Red
    }

    @classmethod
    def render_overlay(
        cls,
        frame: np.ndarray,
        camera_name: str,
        security_state: SecurityState,
        fps: float,
        detections: List[Detection],
        zones: List[Zone],
        latest_event: Optional[IntrusionEvent] = None,
        is_connected: bool = True,
        tracker: Optional[Any] = None,
        is_recorded_mode: bool = False,
        is_webcam_mode: bool = False,
        playback_status: Optional[str] = None,
        controls_hint: Optional[str] = None,
        intrusion_detector: Optional[Any] = None,
        camera_id: Optional[str] = None,
        diagnostics: Optional[Any] = None,
        show_diagnostics: bool = False,
    ) -> np.ndarray:
        """Draws HUD status banner, zones, detections, and alerts onto frame."""
        if frame is None or frame.size == 0:
            # Generate placeholder frame if feed is missing
            canvas = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(
                canvas,
                f"{camera_name}: NO SIGNAL / CONNECTING...",
                (40, 240),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2,
            )
            return canvas

        canvas = frame.copy()
        h, w = canvas.shape[:2]

        # 1. Draw Zones
        for zone in zones:
            if not zone.enabled or len(zone.polygon) < 3:
                continue

            pts = zone.to_pixel_polygon(w, h)
            # Default zone color: Cyan/Yellow; Red if recently triggered
            zone_color = (255, 200, 0)
            if latest_event and latest_event.zone_id == zone.id:
                zone_color = (0, 0, 255)

            # Draw transparent filled polygon
            overlay = canvas.copy()
            cv2.fillPoly(overlay, [pts], zone_color)
            cv2.addWeighted(overlay, 0.20, canvas, 0.80, 0, canvas)
            cv2.polylines(canvas, [pts], isClosed=True, color=zone_color, thickness=2)

            # Zone label at first vertex
            start_pt = pts[0][0]
            label_pos = (max(5, start_pt[0]), max(20, start_pt[1] - 5))
            cv2.putText(
                canvas,
                f"ZONE: {zone.name}",
                label_pos,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                zone_color,
                1,
                cv2.LINE_AA,
            )

        # 2. Draw Person Detections & Tracking IDs
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            box_color = (0, 255, 0)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), box_color, 2)

            # Label with ID, confidence score, and bounding-box height in pixels
            id_text = f"ID:{det.track_id} " if det.track_id is not None else ""
            h_text = f" [H:{det.height_px}px]"
            label = f"{id_text}Person {det.confidence:.2f}{h_text}"
            (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)

            cv2.rectangle(
                canvas,
                (x1, max(0, y1 - th - baseline - 4)),
                (x1 + tw + 4, max(th + 4, y1)),
                box_color,
                -1,
            )
            cv2.putText(
                canvas,
                label,
                (x1 + 2, max(th, y1 - 2)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 0, 0),
                1,
                cv2.LINE_AA,
            )

            # Draw contact points: bottom-center (red, feet) & body-center (cyan, torso)
            cx, cy = det.bottom_center
            cv2.circle(canvas, (int(cx), int(cy)), 4, (0, 0, 255), -1)
            body_cx, body_cy = det.center
            cv2.circle(canvas, (int(body_cx), int(body_cy)), 4, (255, 255, 0), -1)

            # Zone containment & persistence countdown badge
            in_zone_name = None
            in_zone_id = None
            if zones:
                pt_bottom = det.bottom_center_normalized(w, h)
                pt_center = det.center_normalized(w, h)
                for zone in zones:
                    if zone.enabled and (zone.contains_normalized_point(pt_bottom) or zone.contains_normalized_point(pt_center)):
                        in_zone_name = zone.name
                        in_zone_id = zone.id
                        break

            if in_zone_name:
                dwell_sec = 0.0
                min_persist = 2.0
                if intrusion_detector is not None and camera_id is not None:
                    min_persist = intrusion_detector.minimum_persistence_seconds
                    track_key = (camera_id, in_zone_id, det.track_id if det.track_id is not None else 0)
                    if hasattr(intrusion_detector, "_occupancy") and track_key in intrusion_detector._occupancy:
                        dwell_sec = max(0.0, time.time() - intrusion_detector._occupancy[track_key]["first_seen"])

                if security_state == SecurityState.ARMED:
                    if dwell_sec >= min_persist:
                        sub_label = f"ALERT: In '{in_zone_name}' ({dwell_sec:.1f}s)"
                        sub_bg = (0, 0, 200)  # Red
                    else:
                        sub_label = f"Inside '{in_zone_name}' ({dwell_sec:.1f}s / {min_persist:.1f}s)"
                        sub_bg = (0, 140, 255)  # Amber
                else:
                    sub_label = f"Inside '{in_zone_name}' (DISARMED)"
                    sub_bg = (80, 80, 80)  # Grey
            else:
                sub_label = "Outside Zone"
                sub_bg = (50, 50, 50)  # Dark Grey

            (stw, sth), sbase = cv2.getTextSize(sub_label, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
            sy1 = min(h - 4, y2 + sth + 6)
            cv2.rectangle(canvas, (x1, y2 + 2), (x1 + stw + 6, sy1), sub_bg, -1)
            cv2.putText(
                canvas,
                sub_label,
                (x1 + 3, sy1 - 3),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        # 2b. Draw Motion Trajectory Trails
        if tracker is not None:
            for track in tracker.get_all_active_tracks():
                pts_list = list(track.positions)
                if len(pts_list) >= 2:
                    for j in range(1, len(pts_list)):
                        pt_a = (int(pts_list[j - 1][0]), int(pts_list[j - 1][1]))
                        pt_b = (int(pts_list[j][0]), int(pts_list[j][1]))
                        cv2.line(canvas, pt_a, pt_b, (0, 255, 255), 1, cv2.LINE_AA)

        # 3. Top Status Header Bar
        bar_height = 48 if (is_recorded_mode or is_webcam_mode) else 42
        header_overlay = canvas.copy()
        cv2.rectangle(header_overlay, (0, 0), (w, bar_height), (20, 20, 20), -1)
        cv2.addWeighted(header_overlay, 0.85, canvas, 0.15, 0, canvas)

        # Security state badge
        badge_color = cls.COLOR_MAP.get(security_state, (200, 200, 200))
        cv2.rectangle(canvas, (10, 8), (140, 34), badge_color, -1)
        cv2.putText(
            canvas,
            f"STATE: {security_state.value}",
            (16, 26),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )

        # Camera Name & Status
        if is_recorded_mode:
            conn_text = "RECORDED FILE"
            conn_color = (255, 180, 50)  # Amber
        elif is_webcam_mode:
            conn_text = "WEBCAM LIVE" if is_connected else "WEBCAM DISCONNECTED"
            conn_color = (0, 240, 255) if is_connected else (0, 0, 255)  # Cyan
        else:
            conn_text = "LIVE" if is_connected else "OFFLINE"
            conn_color = (0, 255, 0) if is_connected else (0, 0, 255)

        cv2.putText(
            canvas,
            f"{camera_name} [{conn_text}]",
            (155, 26),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            conn_color,
            1,
            cv2.LINE_AA,
        )

        # Prominent Mode Tag
        if is_recorded_mode:
            tag_text = "[RECORDED VIDEO TEST - NOT LIVE CCTV]"
            (tw_tag, th_tag), _ = cv2.getTextSize(tag_text, cv2.FONT_HERSHEY_SIMPLEX, 0.40, 1)
            tag_x = max(155, w - tw_tag - 140)
            cv2.rectangle(canvas, (tag_x - 4, 6), (tag_x + tw_tag + 4, 30), (140, 30, 180), -1)  # Purple tag
            cv2.putText(
                canvas,
                tag_text,
                (tag_x, 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.40,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
        elif is_webcam_mode:
            tag_text = "WEBCAM TEST MODE - NOT CCTV"
            (tw_tag, th_tag), _ = cv2.getTextSize(tag_text, cv2.FONT_HERSHEY_SIMPLEX, 0.40, 1)
            tag_x = max(155, w - tw_tag - 140)
            cv2.rectangle(canvas, (tag_x - 4, 6), (tag_x + tw_tag + 4, 30), (0, 130, 230), -1)  # Vivid Orange/Amber
            cv2.putText(
                canvas,
                tag_text,
                (tag_x, 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.40,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        # Resolution & FPS indicator in header
        res_info = f"Res: {diagnostics.inference_size}px | " if diagnostics and hasattr(diagnostics, "inference_size") else ""
        fps_text = f"{res_info}FPS: {fps:.1f}"
        (tw_fps, _), _ = cv2.getTextSize(fps_text, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
        cv2.putText(
            canvas,
            fps_text,
            (max(w - tw_fps - 15, w - 180), 26),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (220, 220, 220),
            1,
            cv2.LINE_AA,
        )

        # 3b. Diagnostic HUD & Rejected Candidates Overlay (if diagnostics requested)
        if (show_diagnostics or is_recorded_mode) and diagnostics:
            # Draw rejected detections with amber outline and reason
            for rej in getattr(diagnostics, "rejected_detections", []):
                rx1, ry1, rx2, ry2 = rej.bbox
                cv2.rectangle(canvas, (rx1, ry1), (rx2, ry2), (0, 140, 255), 1)  # Amber outline
                rej_tag = f"REJ:{rej.reason[:8]} {rej.confidence:.2f} (H:{rej.height_px}px)"
                cv2.putText(
                    canvas,
                    rej_tag,
                    (rx1, max(12, ry1 - 3)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.34,
                    (0, 165, 255),
                    1,
                    cv2.LINE_AA,
                )

            # Draw Diagnostic Summary Box on upper right
            if show_diagnostics:
                diag_w, diag_h = 245, 74
                dx1 = w - diag_w - 10
                dy1 = bar_height + 8
                diag_overlay = canvas.copy()
                cv2.rectangle(diag_overlay, (dx1, dy1), (dx1 + diag_w, dy1 + diag_h), (25, 25, 25), -1)
                cv2.addWeighted(diag_overlay, 0.85, canvas, 0.15, 0, canvas)
                cv2.rectangle(canvas, (dx1, dy1), (dx1 + diag_w, dy1 + diag_h), (80, 80, 80), 1)

                tiled_str = " (Tiled)" if getattr(diagnostics, "tiled_inference_used", False) else ""
                lines = [
                    f"Inference: {diagnostics.inference_size}px{tiled_str} | {diagnostics.inference_time_ms:.1f}ms",
                    f"Candidates: {diagnostics.total_candidates} (OK: {diagnostics.accepted_count}, Rej: {diagnostics.rejected_count})",
                    f"Tracks: Active: {len(getattr(diagnostics, 'active_track_ids', []))} | Lost: {len(getattr(diagnostics, 'lost_track_ids', []))}",
                ]
                for idx_l, line in enumerate(lines):
                    cv2.putText(
                        canvas,
                        line,
                        (dx1 + 6, dy1 + 18 + idx_l * 20),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.35,
                        (200, 240, 200),
                        1,
                        cv2.LINE_AA,
                    )

        # Sub-header for playback status or webcam processing status
        if is_recorded_mode and playback_status:
            cv2.putText(
                canvas,
                playback_status,
                (16, 44),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (0, 230, 255),  # Cyan
                1,
                cv2.LINE_AA,
            )
        elif is_webcam_mode:
            webcam_sub = playback_status or "Processing: LIVE WEBCAM AI INFERENCE | LOCAL ENGINE"
            cv2.putText(
                canvas,
                webcam_sub,
                (16, 44),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (0, 230, 255),
                1,
                cv2.LINE_AA,
            )

        # 4. Controls Hint Bar (if provided, positioned near bottom)
        if controls_hint:
            hint_y = h - 35 if latest_event else h - 8
            hint_overlay = canvas.copy()
            cv2.rectangle(hint_overlay, (0, hint_y - 18), (w, hint_y + 6), (15, 15, 15), -1)
            cv2.addWeighted(hint_overlay, 0.75, canvas, 0.25, 0, canvas)
            cv2.putText(
                canvas,
                controls_hint,
                (10, hint_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (200, 220, 200),
                1,
                cv2.LINE_AA,
            )

        # 5. Bottom Alert Banner (if recent incident)
        if latest_event:
            bottom_bar_height = 30
            bot_overlay = canvas.copy()
            cv2.rectangle(bot_overlay, (0, h - bottom_bar_height), (w, h), (0, 0, 180), -1)
            cv2.addWeighted(bot_overlay, 0.85, canvas, 0.15, 0, canvas)

            alert_msg = (
                f"ALERT: {latest_event.event_type.value} | Zone: {latest_event.zone_name} | "
                f"Track ID: {latest_event.track_id}"
            )
            cv2.putText(
                canvas,
                alert_msg,
                (15, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        return canvas
