import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

from ..utils.logger import get_logger
from ..utils.helpers import load_config
from ..detection.person_detector import PersonDetector, Detection
from ..tracking.object_tracker import ObjectTracker
from ..intrusion.zone_manager import ZoneManager, Zone
from ..intrusion.intrusion_detector import IntrusionDetector, IntrusionEvent
from ..recording.video_buffer import VideoBuffer
from ..recording.incident_recorder import IncidentRecorder
from ..security.security_controller import SecurityController, SecurityState, ArmCheckResult
from ..camera.visualizer import FeedVisualizer

logger = get_logger("testing.recorded")


def select_video_file_gui() -> Optional[str]:
    """
    Prompts the user to select a recorded shop video file using native Windows file dialog.
    Returns the absolute path if selected, or None if cancelled or unavailable.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        file_path = filedialog.askopenfilename(
            title="Select Recorded Shop Video - ShopGuard AI",
            filetypes=[
                ("Video Files (*.mp4, *.avi, *.mkv, *.mov)", "*.mp4 *.avi *.mkv *.mov *.wmv *.m4v"),
                ("MP4 Videos (*.mp4)", "*.mp4"),
                ("AVI Videos (*.avi)", "*.avi"),
                ("All Files (*.*)", "*.*"),
            ],
        )
        root.destroy()
        if file_path and os.path.isfile(file_path):
            return os.path.abspath(file_path)
    except Exception as e:
        logger.debug(f"GUI file dialog unavailable: {e}")
    return None


def select_video_file(path_arg: Optional[str] = None, prompt_terminal: bool = True) -> str:
    """
    Resolves video file path via CLI argument, GUI file picker dialog, terminal prompt,
    or falls back to default test video feed.
    """
    if path_arg and os.path.isfile(path_arg):
        return os.path.abspath(path_arg)

    # 1. Try Windows GUI dialog
    selected = select_video_file_gui()
    if selected and os.path.isfile(selected):
        return selected

    # 2. Terminal prompt fallback if allowed
    default_test_file = os.path.abspath("data/temporary/test_feed.mp4")
    if prompt_terminal and sys.stdin.isatty():
        try:
            print("\nSelect a recorded shop video file for testing:")
            print(f"Default fallback: {default_test_file}")
            entered = input("Enter video path (or press Enter for default): ").strip()
            if entered and os.path.isfile(entered):
                return os.path.abspath(entered)
        except (EOFError, KeyboardInterrupt):
            pass

    # 3. Check default test video file
    if os.path.isfile(default_test_file):
        return default_test_file

    # 4. Generate default synthetic video if needed
    os.makedirs("data/temporary", exist_ok=True)
    from tools.generate_test_video import generate_synthetic_video
    logger.info("Generating standard synthetic test video at data/temporary/test_feed.mp4...")
    generate_synthetic_video(default_test_file, duration_seconds=10, fps=10, width=640, height=480)
    return default_test_file


class MockCameraManager:
    """Lightweight adapter satisfying SecurityController's camera checks during recorded testing."""

    def __init__(self, camera_id: str, camera_name: str):
        self.camera_id = camera_id
        self.camera_name = camera_name

    def count_total(self) -> int:
        return 1

    def count_connected(self) -> int:
        return 1

    def all_connected(self) -> bool:
        return True

    def get_all_cameras(self) -> Dict[str, Any]:
        return {self.camera_id: self}

    @property
    def is_connected(self) -> bool:
        return True


class RecordedVideoTester:
    """
    Interactive and automated test engine for validating ShopGuard AI on recorded CCTV footage.
    
    Reuses existing modules:
      - PersonDetector (YOLO11n + ByteTrack)
      - ObjectTracker
      - ZoneManager (normalized polygons)
      - IntrusionDetector (foot-contact point, persistence, cooldown)
      - IncidentRecorder & VideoBuffer (pre/post-event MP4 and JSON metadata)
      - SecurityController (DISARMED <-> ARMED state machine)
      - FeedVisualizer (HUD overlay with distinct RECORDED VIDEO banner and controls)
    """

    SPEED_PRESETS = [0.25, 0.5, 1.0, 1.5, 2.0, 4.0]

    def __init__(
        self,
        video_path: str,
        config_path: str = "config/config.yaml",
        zone_file: Optional[str] = None,
        camera_id: str = "cam_recorded",
        camera_name: Optional[str] = None,
        initial_state: SecurityState = SecurityState.DISARMED,
        output_incident_dir: str = "data/incidents",
        show_gui: bool = True,
        auto_arm: bool = False,
        loop: bool = False,
        person_detector: Optional[Any] = None,
        confidence_override: Optional[float] = None,
        imgsz_override: Optional[int] = None,
        tiled_override: Optional[bool] = None,
        min_box_height_override: Optional[int] = None,
        show_diagnostics: bool = False,
    ):
        self.video_path = os.path.abspath(video_path)
        if not os.path.isfile(self.video_path):
            raise FileNotFoundError(f"Recorded video file not found: {self.video_path}")

        self.config_path = config_path
        self.camera_id = camera_id
        self.camera_name = camera_name or f"Recorded: {os.path.basename(self.video_path)}"
        self.show_gui = show_gui
        self.auto_arm = auto_arm
        self.loop = loop
        self.output_incident_dir = output_incident_dir
        self.show_diagnostics = show_diagnostics

        # Open video capture and retrieve metadata
        self._cap = cv2.VideoCapture(self.video_path)
        if not self._cap.isOpened():
            raise RuntimeError(f"OpenCV could not open video file: {self.video_path}")

        self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        detected_fps = self._cap.get(cv2.CAP_PROP_FPS)
        self.fps = detected_fps if detected_fps and detected_fps > 0 else 25.0
        self.duration_seconds = (self.total_frames / self.fps) if self.fps > 0 else 0.0

        logger.info(
            f"[RECORDED VIDEO TEST] Loaded '{self.video_path}' | "
            f"Resolution: {self.width}x{self.height} | Frames: {self.total_frames} | "
            f"FPS: {self.fps:.1f} | Duration: {self.duration_seconds:.1f}s"
        )
        logger.info("[RECORDED VIDEO TEST] NOTE: RTSP connectivity is NOT tested in recorded-video mode.")

        # Load configurations
        self.config = load_config(self.config_path) if os.path.isfile(self.config_path) else {}
        sec_cfg = self.config.get("security", {})
        ai_cfg = self.config.get("ai", {})
        rec_cfg = self.config.get("recording", {})
        zones_cfg = self.config.get("zones", {})

        # 1. Person Detector & Tracker
        conf_thresh = (
            confidence_override
            if confidence_override is not None
            else sec_cfg.get("confidence_threshold", 0.45)
        )
        if person_detector is not None:
            self.person_detector = person_detector
        else:
            model_path = ai_cfg.get("model", "models/yolo11n.pt")
            imgsz = (
                imgsz_override
                if imgsz_override is not None
                else ai_cfg.get("inference_size", 640)
            )
            enable_tiled = (
                tiled_override
                if tiled_override is not None
                else ai_cfg.get("enable_tiled_inference", False)
            )
            min_box_h = (
                min_box_height_override
                if min_box_height_override is not None
                else ai_cfg.get("min_box_height_px", 15)
            )
            min_box_w = ai_cfg.get("min_box_width_px", 10)
            rect_inf = ai_cfg.get("rect_inference", True)
            t_grid = tuple(ai_cfg.get("tiled_grid", [2, 2]))
            t_overlap = float(ai_cfg.get("tiled_overlap", 0.20))

            self.person_detector = PersonDetector(
                model_path=model_path,
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
        self.tracker = ObjectTracker()

        # 2. Zone Manager
        actual_zones_file = zone_file or zones_cfg.get("configuration_file", "config/zones.json")
        if not os.path.isfile(actual_zones_file):
            actual_zones_file = "config/zones.example.json"
        self.zone_manager = ZoneManager(actual_zones_file)

        # Ensure our recorded camera has valid zones
        if not self.zone_manager.has_enabled_zones(self.camera_id):
            all_zones = self.zone_manager.get_all_zones()
            if all_zones:
                # Borrow zones from the first configured camera
                first_cam_id = next(iter(all_zones.keys()))
                for z in all_zones[first_cam_id]:
                    self.zone_manager.add_zone(self.camera_id, z)
                logger.info(f"Adopted {len(all_zones[first_cam_id])} zones from '{first_cam_id}' for testing.")
            else:
                # Add default floor test zone
                default_zone = Zone(
                    id="zone_floor_test",
                    name="Recorded Test Floor Area",
                    polygon=[(0.15, 0.35), (0.85, 0.35), (0.85, 0.90), (0.15, 0.90)],
                    enabled=True,
                )
                self.zone_manager.add_zone(self.camera_id, default_zone)
                logger.info("Created default restricted floor zone for recorded video evaluation.")

        # 3. Intrusion Detector
        self.intrusion_detector = IntrusionDetector(
            minimum_persistence_seconds=sec_cfg.get("minimum_persistence_seconds", 2.0),
            event_cooldown_seconds=sec_cfg.get("event_cooldown_seconds", 30.0),
            confidence_threshold=conf_thresh,
        )

        # 4. Incident Recorder & Circular Buffer
        pre_sec = rec_cfg.get("pre_event_seconds", 5.0)
        post_sec = rec_cfg.get("post_event_seconds", 10.0)
        self.incident_recorder = IncidentRecorder(
            output_directory=self.output_incident_dir,
            pre_event_seconds=pre_sec,
            post_event_seconds=post_sec,
            fps=self.fps,
            enabled=True,
        )
        self.video_buffer = VideoBuffer(buffer_seconds=pre_sec + 2.0, fps=self.fps)

        # Playback and execution state
        self._running = False
        self.is_paused = False
        self.speed_index = 2  # default 1.0x (index 2 in [0.25, 0.5, 1.0, 1.5, 2.0, 4.0])
        self.playback_speed = self.SPEED_PRESETS[self.speed_index]
        self.current_frame_idx = 0
        self.simulated_start_time = time.time()
        self.last_event: Optional[IntrusionEvent] = None
        self.triggered_events: List[IntrusionEvent] = []
        self.step_one_frame = False

        # 5. Security Controller
        self.security_controller = SecurityController(initial_state=initial_state)
        self._mock_cam_mgr = MockCameraManager(self.camera_id, self.camera_name)
        self.security_controller.bind_dependencies(
            camera_manager=self._mock_cam_mgr,
            person_detector=self.person_detector,
            zone_manager=self.zone_manager,
            is_processing_active=lambda: self._running or (self._cap is not None and self._cap.isOpened()),
        )

        # Arm if requested
        if self.auto_arm:
            self.security_controller.arm()

    def arm(self) -> Tuple[bool, str, Optional[ArmCheckResult]]:
        """Arms the security system during recorded video testing."""
        return self.security_controller.arm()

    def disarm(self) -> Tuple[bool, str]:
        """Disarms the security system during recorded video testing."""
        return self.security_controller.disarm()

    def pause(self) -> None:
        """Pauses video playback."""
        self.is_paused = True

    def resume(self) -> None:
        """Resumes video playback."""
        self.is_paused = False

    def restart(self) -> None:
        """Restarts playback from frame 0."""
        with self.video_buffer._lock:
            self.video_buffer._buffer.clear()
        self.tracker.reset()
        self.intrusion_detector.reset()
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self.current_frame_idx = 0
        self.simulated_start_time = time.time()
        self.last_event = None
        logger.info("[RECORDED VIDEO TEST] Playback restarted from frame 0.")

    def set_speed(self, speed: float) -> None:
        """Sets playback speed multiplier."""
        self.playback_speed = max(0.1, float(speed))

    def step_forward(self) -> None:
        """Steps forward by a single frame when paused."""
        self.step_one_frame = True

    def stop(self) -> None:
        """Stops the test runner and releases resources."""
        self._running = False
        if self._cap is not None:
            self._cap.release()
        self.incident_recorder.shutdown()
        if self.show_gui:
            cv2.destroyAllWindows()
        logger.info("[RECORDED VIDEO TEST] Runner stopped cleanly.")

    def run(self, max_frames: Optional[int] = None) -> Dict[str, Any]:
        """
        Executes frame-by-frame analysis of the recorded video.
        
        Args:
            max_frames: Optional frame limit (useful for unit tests).
            
        Returns:
            Dict containing test execution statistics.
        """
        self._running = True
        window_name = f"ShopGuard AI - [RECORDED VIDEO TEST] - {os.path.basename(self.video_path)}"
        zones = self.zone_manager.get_zones(self.camera_id, enabled_only=True)

        frames_analyzed = 0
        detections_count = 0
        last_frame_annotated = None

        logger.info(f"[RECORDED VIDEO TEST] Starting evaluation (Initial State: {self.security_controller.state.value})")

        try:
            while self._running:
                # Handle paused state
                if self.is_paused and not self.step_one_frame:
                    if self.show_gui and last_frame_annotated is not None:
                        # Render paused HUD
                        paused_frame = FeedVisualizer.render_overlay(
                            frame=last_frame_annotated,
                            camera_name=self.camera_name,
                            security_state=self.security_controller.state,
                            fps=self.fps,
                            detections=[],
                            zones=zones,
                            latest_event=self.last_event,
                            is_connected=True,
                            tracker=self.tracker,
                            is_recorded_mode=True,
                            playback_status=f"PAUSED | SPEED: {self.playback_speed:.2f}x | FRAME: {self.current_frame_idx}/{self.total_frames}",
                            controls_hint="Controls: [Space] Play  [A] Arm  [D] Disarm  [R] Restart  [N] Step  [Q] Quit",
                        )
                        cv2.imshow(window_name, paused_frame)
                        key = cv2.waitKey(50) & 0xFF
                        self._handle_key(key)
                        continue
                    else:
                        time.sleep(0.05)
                        continue

                # Read next frame
                ret, frame = self._cap.read()
                if not ret or frame is None:
                    logger.info("[RECORDED VIDEO TEST] Reached end of video file (EOF).")
                    if self.loop:
                        self.restart()
                        continue
                    else:
                        break

                self.current_frame_idx += 1
                frames_analyzed += 1
                self.step_one_frame = False

                # Deterministic simulated timestamp based on frame index & native FPS
                simulated_time = self.simulated_start_time + (self.current_frame_idx / self.fps)

                # Feed in-memory rolling buffer & active incident writer
                self.video_buffer.append(frame, simulated_time)
                self.incident_recorder.on_new_frame(self.camera_id, frame, simulated_time)

                # Person Detection & Tracking
                detections = self.person_detector.detect_and_track(frame, timestamp=simulated_time)
                detections_count += len(detections)
                self.tracker.update(detections, timestamp=simulated_time)

                # Evaluate Intrusion Zones
                is_armed = self.security_controller.is_armed
                events = self.intrusion_detector.process_frame_detections(
                    camera_id=self.camera_id,
                    detections=detections,
                    zones=zones,
                    frame_width=self.width,
                    frame_height=self.height,
                    is_armed=is_armed,
                    timestamp=simulated_time,
                )

                # Handle Simulated Intrusion Events
                for evt in events:
                    self.last_event = evt
                    self.triggered_events.append(evt)
                    logger.warning(
                        f"[SIMULATED INTRUSION] Detected person in zone '{evt.zone_name}' "
                        f"(Track ID: {evt.track_id}, Confidence: {evt.confidence:.2f})"
                    )

                    # Extract pre-event frames
                    pre_start = evt.timestamp - self.incident_recorder.pre_event_seconds
                    pre_frames = self.video_buffer.get_frames(start_timestamp=pre_start)

                    # Trigger incident recording tagged as recorded_video simulation
                    self.incident_recorder.trigger_incident(
                        event=evt,
                        camera_name=self.camera_name,
                        pre_frames=pre_frames,
                        source_type="recorded_video",
                        simulation_mode=True,
                        rtsp_verified=False,
                    )

                # Visual HUD Overlay
                playback_str = (
                    f"{'PAUSED' if self.is_paused else 'PLAYING'} | "
                    f"SPEED: {self.playback_speed:.2f}x | "
                    f"FRAME: {self.current_frame_idx}/{self.total_frames} "
                    f"({(self.current_frame_idx / self.fps):.1f}s/{(self.duration_seconds):.1f}s)"
                )
                controls_str = (
                    "Controls: [Space] Pause/Play | [A] Arm | [D] Disarm | [R] Restart | [+/-] Speed | [N] Step | [Q] Quit"
                )

                annotated = FeedVisualizer.render_overlay(
                    frame=frame,
                    camera_name=self.camera_name,
                    security_state=self.security_controller.state,
                    fps=self.fps * self.playback_speed,
                    detections=detections,
                    zones=zones,
                    latest_event=self.last_event,
                    is_connected=True,
                    tracker=self.tracker,
                    is_recorded_mode=True,
                    playback_status=playback_str,
                    controls_hint=controls_str,
                    diagnostics=getattr(self.person_detector, "get_diagnostics", lambda: None)(),
                    show_diagnostics=self.show_diagnostics,
                )
                last_frame_annotated = frame.copy()

                if self.show_gui:
                    cv2.imshow(window_name, annotated)
                    delay_ms = max(1, int(1000.0 / (self.fps * self.playback_speed)))
                    key = cv2.waitKey(delay_ms) & 0xFF
                    self._handle_key(key)

                if max_frames and frames_analyzed >= max_frames:
                    break

        finally:
            self.stop()

        return {
            "video_path": self.video_path,
            "total_frames_analyzed": frames_analyzed,
            "total_detections": detections_count,
            "incidents_count": len(self.triggered_events),
            "incidents": self.triggered_events,
            "final_security_state": self.security_controller.state.value,
        }

    def _handle_key(self, key: int) -> None:
        """Processes OpenCV keyboard shortcuts during playback."""
        if key in (ord("q"), ord("Q"), 27):  # 'q' or ESC
            logger.info("[RECORDED VIDEO TEST] Quit requested by user.")
            self._running = False

        elif key == ord(" "):  # Spacebar
            self.is_paused = not self.is_paused
            logger.info(f"[RECORDED VIDEO TEST] Playback {'PAUSED' if self.is_paused else 'RESUMED'}.")

        elif key in (ord("a"), ord("A")):  # Arm
            success, msg, _ = self.arm()
            logger.info(f"[RECORDED VIDEO TEST] ARM REQUEST: {msg}")

        elif key in (ord("d"), ord("D")):  # Disarm
            success, msg = self.disarm()
            logger.info(f"[RECORDED VIDEO TEST] DISARM REQUEST: {msg}")

        elif key in (ord("r"), ord("R")):  # Restart
            self.restart()

        elif key in (ord("+"), ord("="), ord("]")):  # Increase speed
            if self.speed_index < len(self.SPEED_PRESETS) - 1:
                self.speed_index += 1
                self.playback_speed = self.SPEED_PRESETS[self.speed_index]
                logger.info(f"[RECORDED VIDEO TEST] Playback speed set to {self.playback_speed}x")

        elif key in (ord("-"), ord("_"), ord("[")):  # Decrease speed
            if self.speed_index > 0:
                self.speed_index -= 1
                self.playback_speed = self.SPEED_PRESETS[self.speed_index]
                logger.info(f"[RECORDED VIDEO TEST] Playback speed set to {self.playback_speed}x")

        elif key in (ord("n"), ord("N"), ord(".")):  # Step 1 frame
            if self.is_paused:
                self.step_forward()
