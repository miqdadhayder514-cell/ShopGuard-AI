"""
ShopGuard AI - Main Application Entry Point
Phase 1: Local AI CCTV Security Engine
"""

import argparse
import os
import sys
import threading
import time
from typing import Dict, Optional
import cv2

from shopguard.utils.logger import setup_logger, mask_url
from shopguard.utils.helpers import load_config
from shopguard.camera.camera_manager import CameraManager
from shopguard.camera.visualizer import FeedVisualizer
from shopguard.detection.person_detector import PersonDetector
from shopguard.tracking.object_tracker import ObjectTracker
from shopguard.intrusion.zone_manager import ZoneManager
from shopguard.intrusion.intrusion_detector import IntrusionDetector, IntrusionEvent
from shopguard.recording.video_buffer import VideoBuffer
from shopguard.recording.incident_recorder import IncidentRecorder
from shopguard.security.security_controller import SecurityController, SecurityState
from shopguard.monitoring.health_monitor import HealthMonitor
from shopguard.notifications.fcm_notifier import fcm_notifier


class ShopGuardEngine:
    """
    Main orchestration engine connecting cameras, AI detection, tracking,
    zone monitoring, incident recording, and manual security controls.
    """

    def __init__(
        self,
        config_path: str = "config/config.yaml",
        video_override: Optional[str] = None,
        webcam_override: Optional[int] = None,
        show_gui: bool = True,
        confidence_override: Optional[float] = None,
        persistence_override: Optional[float] = None,
        zone_preset: Optional[str] = None,
        imgsz_override: Optional[int] = None,
        tiled_override: Optional[bool] = None,
        min_box_height_override: Optional[int] = None,
        show_diagnostics: bool = False,
    ):
        self.config_path = config_path
        self.video_override = video_override
        self.webcam_override = webcam_override
        self.is_webcam_mode = (webcam_override is not None)
        self.show_gui = show_gui
        self.confidence_override = confidence_override
        self.persistence_override = persistence_override
        self.zone_preset = zone_preset
        self.imgsz_override = imgsz_override
        self.tiled_override = tiled_override
        self.min_box_height_override = min_box_height_override
        self.show_diagnostics = show_diagnostics

        # 1. Setup logging
        self.logger = setup_logger("data/logs")
        self.logger.info("Initializing ShopGuard AI Engine (Phase 1)...")

        # 2. Load Configuration
        self.config = load_config(self.config_path)

        # Allow CLI override for camera source (useful for testing with local video file)
        if self.video_override:
            if "cameras" in self.config and len(self.config["cameras"]) > 0:
                self.logger.info(f"Overriding primary camera source with local test video: {self.video_override}")
                self.config["cameras"][0]["source"] = self.video_override
                self.config["cameras"][0]["name"] = "Test Video Feed"

        # Allow CLI override for laptop webcam
        if self.webcam_override is not None:
            from shopguard.camera.stream_reader import check_webcam_available
            is_avail, msg, res = check_webcam_available(self.webcam_override)
            if not is_avail:
                self.logger.error(f"[WEBCAM UNAVAILABLE] {msg}")
                print(f"\n[ERROR] Laptop webcam index {self.webcam_override} could not be opened:\n  {msg}\n")
                print("Tips for Windows laptop webcam testing:")
                print("  1. Verify the webcam is not disabled (check physical privacy shutter / Fn key).")
                print("  2. Open Windows Settings -> Privacy & security -> Camera, and turn on 'Camera access'.")
                print("  3. Ensure no other application (Zoom, Teams, Skype, Browser) is currently using the camera.")
                print("  4. If multiple cameras exist, try another index (e.g. --webcam 1).\n")
                raise RuntimeError(f"Webcam index {self.webcam_override} is unavailable: {msg}")

            w_res, h_res = res if res else (640, 480)
            self.logger.info(
                f"Configuring laptop webcam device index {self.webcam_override} ({w_res}x{h_res}) as primary feed..."
            )
            if "cameras" in self.config and len(self.config["cameras"]) > 0:
                self.config["cameras"][0]["source"] = f"webcam:{self.webcam_override}"
                self.config["cameras"][0]["name"] = f"Laptop Webcam {self.webcam_override}"
            else:
                self.config["cameras"] = [{
                    "id": "cam_webcam",
                    "name": f"Laptop Webcam {self.webcam_override}",
                    "source": f"webcam:{self.webcam_override}",
                    "enabled": True,
                    "fps": 15.0,
                }]

        sec_cfg = self.config.get("security", {})
        ai_cfg = self.config.get("ai", {})
        rec_cfg = self.config.get("recording", {})
        zones_cfg = self.config.get("zones", {})

        # 3. Initialize Camera Manager
        self.camera_manager = CameraManager()
        self.camera_manager.load_from_config(self.config)

        # 4. Initialize Zone Manager
        zones_file = zones_cfg.get("configuration_file", "config/zones.example.json")
        self.zone_manager = ZoneManager(zones_file)

        # Zone configuration logic
        if self.zone_preset == "full":
            from shopguard.intrusion.zone_manager import Zone
            for cam_id in self.camera_manager.get_all_cameras().keys():
                self.zone_manager.set_zones(
                    cam_id,
                    [
                        Zone(
                            id="zone_room_full",
                            name="Room Protected Area",
                            polygon=[(0.05, 0.10), (0.95, 0.10), (0.95, 0.98), (0.05, 0.98)],
                            enabled=True,
                        )
                    ],
                )
        elif self.is_webcam_mode:
            from shopguard.intrusion.zone_manager import Zone
            for cam_id in self.camera_manager.get_all_cameras().keys():
                if not self.zone_manager.has_enabled_zones(cam_id):
                    all_z = self.zone_manager.get_all_zones()
                    if all_z:
                        first_k = next(iter(all_z.keys()))
                        for z in all_z[first_k]:
                            self.zone_manager.add_zone(cam_id, z)
                    else:
                        self.zone_manager.add_zone(
                            cam_id,
                            Zone(
                                id="zone_webcam_test",
                                name="Webcam Restricted Area",
                                polygon=[(0.10, 0.20), (0.90, 0.20), (0.90, 0.98), (0.10, 0.98)],
                                enabled=True,
                            ),
                        )

        # 5. Initialize Person Detector
        conf_thresh = (
            self.confidence_override
            if self.confidence_override is not None
            else sec_cfg.get("confidence_threshold", 0.45)
        )
        imgsz = (
            self.imgsz_override
            if self.imgsz_override is not None
            else ai_cfg.get("inference_size", 640)
        )
        enable_tiled = (
            self.tiled_override
            if self.tiled_override is not None
            else ai_cfg.get("enable_tiled_inference", False)
        )
        min_box_h = (
            self.min_box_height_override
            if self.min_box_height_override is not None
            else ai_cfg.get("min_box_height_px", 15)
        )
        min_box_w = ai_cfg.get("min_box_width_px", 10)
        rect_inf = ai_cfg.get("rect_inference", True)
        t_grid = tuple(ai_cfg.get("tiled_grid", [2, 2]))
        t_overlap = float(ai_cfg.get("tiled_overlap", 0.20))

        self.person_detector = PersonDetector(
            model_path=ai_cfg.get("model", "models/yolo11n.pt"),
            confidence_threshold=conf_thresh,
            device=ai_cfg.get("device", "cpu"),
            use_tracking=True,
            imgsz=imgsz,
            rect=rect_inf,
            min_box_height_px=min_box_h,
            min_box_width_px=min_box_w,
            enable_tiled_inference=enable_tiled,
            tiled_grid=t_grid,
            tiled_overlap=t_overlap,
        )

        # 6. Initialize Intrusion Detector
        persist_sec = (
            self.persistence_override
            if self.persistence_override is not None
            else sec_cfg.get("minimum_persistence_seconds", 2.0)
        )
        self.intrusion_detector = IntrusionDetector(
            minimum_persistence_seconds=persist_sec,
            event_cooldown_seconds=sec_cfg.get("event_cooldown_seconds", 30.0),
            confidence_threshold=conf_thresh,
        )

        # 7. Initialize Incident Recorder & Video Buffers
        self.incident_recorder = IncidentRecorder(
            output_directory=rec_cfg.get("output_directory", "data/incidents"),
            pre_event_seconds=rec_cfg.get("pre_event_seconds", 10.0),
            post_event_seconds=rec_cfg.get("post_event_seconds", 15.0),
            fps=ai_cfg.get("processing_fps", 5.0),
            enabled=rec_cfg.get("enabled", True),
        )

        # Rolling video buffers and Object Trackers per camera
        self.video_buffers: Dict[str, VideoBuffer] = {}
        self.trackers: Dict[str, ObjectTracker] = {}
        target_fps = ai_cfg.get("processing_fps", 5.0)
        pre_sec = rec_cfg.get("pre_event_seconds", 10.0)
        for cam_id in self.camera_manager.get_all_cameras().keys():
            self.video_buffers[cam_id] = VideoBuffer(buffer_seconds=pre_sec + 2.0, fps=target_fps)
            self.trackers[cam_id] = ObjectTracker()

        # 8. Initialize Security Controller
        init_state_name = sec_cfg.get("initial_state", "DISARMED").upper()
        initial_state = SecurityState.DISARMED
        try:
            initial_state = SecurityState(init_state_name)
        except ValueError:
            initial_state = SecurityState.DISARMED

        self.security_controller = SecurityController(initial_state=initial_state)
        self.security_controller.bind_dependencies(
            camera_manager=self.camera_manager,
            person_detector=self.person_detector,
            zone_manager=self.zone_manager,
            is_processing_active=self.is_monitoring_operational,
            is_processing_worker_active=self.is_processing_worker_active,
        )

        # 9. Health Monitor
        self.health_monitor = HealthMonitor(
            camera_manager=self.camera_manager,
            person_detector=self.person_detector,
            security_controller=self.security_controller,
            storage_path=rec_cfg.get("output_directory", "data/incidents"),
        )

        # 10. Firebase Push Notification Manager
        self.fcm_notifier = fcm_notifier

        # Processing loop state
        self._running = False
        self._proc_thread: Optional[threading.Thread] = None
        self._lifecycle_lock = threading.RLock()
        self._last_processed_frame_times: Dict[str, float] = {}
        self.latest_events: Dict[str, Optional[IntrusionEvent]] = {}
        self.target_fps = float(ai_cfg.get("processing_fps", 5.0))

    def start(self) -> None:
        """Starts camera readers and exactly one background processing thread."""
        with self._lifecycle_lock:
            if self._proc_thread and self._proc_thread.is_alive():
                if self._running:
                    return
                raise RuntimeError(
                    "The previous ShopGuard processing worker is still stopping; "
                    "refusing to start a duplicate worker."
                )

            self._running = True
            self.camera_manager.start_all()
            self._proc_thread = threading.Thread(
                target=self._processing_loop,
                name="ShopGuardProcessingLoop",
                daemon=True,
            )
            self._proc_thread.start()
        self.logger.info("ShopGuard AI CCTV Processing Loop started successfully.")

    def stop(self) -> None:
        """Shuts down monitoring and all engine components gracefully."""
        self.stop_monitoring()
        self.incident_recorder.shutdown()
        cv2.destroyAllWindows()
        self.logger.info("ShopGuard AI Engine stopped cleanly.")

    def stop_monitoring(self) -> None:
        """Stops camera and inference workers while keeping the API-owned engine reusable."""
        self.logger.info("Stopping ShopGuard camera monitoring...")
        self.security_controller.disarm()
        with self._lifecycle_lock:
            self._running = False
            proc_thread = self._proc_thread

        if proc_thread and proc_thread.is_alive():
            proc_thread.join(timeout=3.0)

        self.camera_manager.stop_all()
        self._last_processed_frame_times.clear()
        self.logger.info("ShopGuard camera monitoring stopped; agent API remains available.")

    def is_monitoring_operational(self) -> bool:
        """Checks that the AI loop is alive and has recently processed every enabled camera."""
        if not self.is_processing_worker_active() or not self.camera_manager.all_ready():
            return False

        now = time.time()
        processing_lag_limit = max(2.0, 3.0 / max(self.target_fps, 0.1))
        for camera_id, reader in self.camera_manager.get_all_cameras().items():
            max_age = max(5.0, float(getattr(reader, "connection_timeout", 10.0)))
            last_processed = self._last_processed_frame_times.get(camera_id)
            if (
                last_processed is None
                or now - last_processed > max_age
                or reader.last_frame_time - last_processed > processing_lag_limit
            ):
                return False
        return True

    def is_processing_worker_active(self) -> bool:
        """Checks for a live inference worker that has recently processed a camera frame."""
        thread = self._proc_thread
        if (
            not self._running
            or thread is None
            or not thread.is_alive()
            or not self.person_detector.is_loaded
        ):
            return False

        now = time.time()
        processing_lag_limit = max(2.0, 3.0 / max(self.target_fps, 0.1))
        for camera_id, reader in self.camera_manager.get_all_cameras().items():
            if not reader.is_ready:
                continue
            max_age = max(5.0, float(getattr(reader, "connection_timeout", 10.0)))
            last_processed = self._last_processed_frame_times.get(camera_id)
            if (
                last_processed is not None
                and now - last_processed <= max_age
                and reader.last_frame_time - last_processed <= processing_lag_limit
            ):
                return True
        return False

    def wait_until_monitoring_ready(self, timeout_seconds: float) -> bool:
        """Waits for every enabled camera to produce a frame consumed by person inference."""
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        while True:
            if self.is_monitoring_operational():
                return True
            thread = self._proc_thread
            if not self._running or thread is None or not thread.is_alive():
                return False
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.1)

    def _processing_loop(self) -> None:
        try:
            self._run_processing_loop()
        except Exception as exc:
            self.logger.exception(f"ShopGuard AI processing loop terminated unexpectedly: {exc}")
            self._running = False
            self.security_controller.monitoring_failed(str(exc))

    def _run_processing_loop(self) -> None:
        """Core AI inference and security event evaluation loop."""
        interval = 1.0 / self.target_fps

        fps_timer = time.time()
        fps_counter = 0
        measured_fps = self.target_fps

        while self._running:
            loop_start = time.time()

            # Dynamically fetch current active cameras to support runtime addition/removal
            active_cameras = dict(self.camera_manager.get_all_cameras())

            # Update camera connectivity and sync security controller health
            self.security_controller.update_camera_health()
            for cam_id, reader in list(active_cameras.items()):
                # Ensure rolling buffer and tracker are initialized for dynamic cameras
                if cam_id not in self.video_buffers:
                    self.video_buffers[cam_id] = VideoBuffer(
                        buffer_seconds=self.incident_recorder.pre_event_seconds + 2.0,
                        fps=self.target_fps,
                    )
                if cam_id not in self.trackers:
                    self.trackers[cam_id] = ObjectTracker()
                ret, frame, frame_ts = reader.read()
                if not ret or frame is None:
                    continue

                h, w = frame.shape[:2]

                # Update rolling pre-event buffer
                if cam_id in self.video_buffers:
                    self.video_buffers[cam_id].append(frame, frame_ts)

                # Feed active recording sessions
                self.incident_recorder.on_new_frame(cam_id, frame, frame_ts)

                # Run Person Detection & Tracking
                detections = self.person_detector.detect_and_track(frame, timestamp=frame_ts)
                self._last_processed_frame_times[cam_id] = frame_ts

                # Update Object Tracker
                if cam_id in self.trackers:
                    self.trackers[cam_id].update(detections, timestamp=frame_ts)

                # Evaluate Intrusion Zones
                zones = self.zone_manager.get_zones(cam_id, enabled_only=True)
                events = self.security_controller.evaluate_intrusions(
                    self.intrusion_detector,
                    camera_id=cam_id,
                    detections=detections,
                    zones=zones,
                    frame_width=w,
                    frame_height=h,
                    timestamp=frame_ts,
                )

                # Handle Intrusion Events
                for evt in events:
                    self.latest_events[cam_id] = evt
                    print(
                        f"\n>>> [INTRUSION ALERT] Person detected in '{evt.zone_name}'! "
                        f"(Track ID: {evt.track_id}, Confidence: {evt.confidence:.2f}, Persist: {evt.persistence_seconds:.1f}s) "
                        f"Recording incident clip...\n"
                    )
                    # Extract pre-event frames from circular buffer
                    pre_frames = []
                    if cam_id in self.video_buffers:
                        pre_start = evt.timestamp - self.incident_recorder.pre_event_seconds
                        pre_frames = self.video_buffers[cam_id].get_frames(start_timestamp=pre_start)

                    self.incident_recorder.trigger_incident(
                        event=evt,
                        camera_name=reader.name,
                        pre_frames=pre_frames,
                        source_type="webcam" if self.is_webcam_mode else "live_cctv",
                        simulation_mode=self.is_webcam_mode,
                        rtsp_verified=False if self.is_webcam_mode else True,
                    )

                    # Real-time Push Notification Dispatch to mobile devices
                    if self.fcm_notifier:
                        try:
                            self.fcm_notifier.send_security_alert(
                                incident_id=evt.event_id,
                                event_type=evt.event_type.value,
                                camera_name=reader.name,
                                camera_id=cam_id,
                                confidence=evt.confidence,
                            )
                        except Exception as notif_err:
                            self.logger.error(f"FCM notification dispatch failed for incident {evt.event_id}: {notif_err}")

                # Visual Monitoring Display
                if self.show_gui:
                    annotated = FeedVisualizer.render_overlay(
                        frame=frame,
                        camera_name=reader.name,
                        security_state=self.security_controller.state,
                        fps=measured_fps,
                        detections=detections,
                        zones=zones,
                        latest_event=self.latest_events.get(cam_id),
                        is_connected=reader.is_connected,
                        tracker=self.trackers.get(cam_id),
                        is_webcam_mode=self.is_webcam_mode,
                        controls_hint="Controls: [A] Arm  [D] Disarm  [S] Status  [Q] Quit" if self.is_webcam_mode else None,
                        intrusion_detector=self.intrusion_detector,
                        camera_id=cam_id,
                        diagnostics=getattr(self.person_detector, "get_diagnostics", lambda: None)(),
                        show_diagnostics=self.show_diagnostics,
                    )
                    win_title = f"ShopGuard AI - [WEBCAM] {reader.name}" if self.is_webcam_mode else f"ShopGuard AI - {reader.name}"
                    cv2.imshow(win_title, annotated)

            # Compute measured FPS
            fps_counter += 1
            if time.time() - fps_timer >= 1.0:
                measured_fps = fps_counter / (time.time() - fps_timer)
                fps_counter = 0
                fps_timer = time.time()

            # Handle OpenCV window events
            if self.show_gui:
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):  # 'q' or ESC
                    self.logger.info("GUI close requested via keyboard.")
                    self._running = False
                    break
                elif key in (ord("a"), ord("A")):
                    success, msg, _ = self.security_controller.arm()
                    self.logger.info(f"ARM REQUEST: {msg}")
                    print(f"\n[SECURITY] {msg}\n")
                elif key in (ord("d"), ord("D")):
                    success, msg = self.security_controller.disarm()
                    self.logger.info(f"DISARM REQUEST: {msg}")
                    print(f"\n[SECURITY] {msg}\n")
                elif key in (ord("s"), ord("S")):
                    self.health_monitor.print_status_summary()

            # Frame rate pacing
            elapsed = time.time() - loop_start
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def run_cli(self) -> None:
        """Interactive terminal command interface for shop security control."""
        print("\n" + "=" * 60)
        print("          SHOPGUARD AI - CCTV INTRUSION ENGINE")
        print("=" * 60)
        print("  Commands:")
        print("    arm     - Run security checks and activate night security")
        print("    disarm  - Deactivate night security (feeds remain active)")
        print("    status  - Print comprehensive system health report")
        print("    exit    - Safely shut down the security engine")
        print("=" * 60 + "\n")

        self.start()

        try:
            while self._running:
                try:
                    cmd = input("ShopGuard> ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    break

                if not cmd:
                    continue

                if cmd == "arm":
                    success, msg, details = self.security_controller.arm()
                    if success:
                        print(f"\n[OK] {msg}\n")
                    else:
                        print(f"\n[FAILED] {msg}\n")

                elif cmd == "disarm":
                    success, msg = self.security_controller.disarm()
                    print(f"\n[OK] {msg}\n")

                elif cmd == "status":
                    self.health_monitor.print_status_summary()

                elif cmd in ("exit", "quit", "q"):
                    print("Exiting ShopGuard AI...")
                    break
                else:
                    print(f"Unknown command: '{cmd}'. Available: arm, disarm, status, exit")

        finally:
            self.stop()


def main():
    parser = argparse.ArgumentParser(description="ShopGuard AI CCTV Security Engine")
    parser.add_argument("--config", default="config/config.yaml", help="Path to config.yaml")
    parser.add_argument("--video", default=None, help="Local video file path to simulate camera")
    parser.add_argument(
        "--test-video",
        nargs="?",
        const="",
        default=None,
        help="Launch interactive recorded-video testing mode. Optionally specify video file path.",
    )
    parser.add_argument(
        "--recorded-mode",
        action="store_true",
        help="Run video input in dedicated recorded testing mode with interactive playback controls.",
    )
    parser.add_argument(
        "--webcam",
        nargs="?",
        const=0,
        type=int,
        default=None,
        help="Run live laptop webcam testing mode (default camera index 0, or specify e.g. --webcam 1).",
    )
    parser.add_argument(
        "--auto-arm",
        action="store_true",
        help="Automatically arm the system at startup (useful for testing).",
    )
    parser.add_argument("--no-gui", action="store_true", help="Run in headless mode without OpenCV windows")
    parser.add_argument("--conf", type=float, default=None, help="Override YOLO person confidence threshold (e.g. 0.25)")
    parser.add_argument("--imgsz", type=int, default=None, help="YOLO inference resolution (e.g. 640, 960, 1280)")
    parser.add_argument("--tiled", action="store_true", help="Enable tiled / sliced inference for high-res streams")
    parser.add_argument("--min-height", type=int, default=None, help="Minimum person bounding-box height in pixels")
    parser.add_argument("--diagnostics", action="store_true", help="Display realtime inference and rejection diagnostics on HUD")
    args = parser.parse_args()

    # Route to recorded video testing mode if requested
    if args.test_video is not None or args.recorded_mode:
        from shopguard.testing.recorded_video_tester import RecordedVideoTester, select_video_file
        target_path = args.video if args.video else (args.test_video if args.test_video else None)
        resolved_video = select_video_file(target_path)
        tester = RecordedVideoTester(
            video_path=resolved_video,
            config_path=args.config,
            show_gui=not args.no_gui,
            auto_arm=args.auto_arm,
            confidence_override=args.conf,
            imgsz_override=args.imgsz,
            tiled_override=args.tiled,
            min_box_height_override=args.min_height,
            show_diagnostics=args.diagnostics,
        )
        tester.run()
        return

    engine = ShopGuardEngine(
        config_path=args.config,
        video_override=args.video,
        webcam_override=args.webcam,
        show_gui=not args.no_gui,
        confidence_override=args.conf,
        imgsz_override=args.imgsz,
        tiled_override=args.tiled,
        min_box_height_override=args.min_height,
        show_diagnostics=args.diagnostics,
    )
    if args.auto_arm:
        engine.security_controller.arm()
    engine.run_cli()


if __name__ == "__main__":
    main()
