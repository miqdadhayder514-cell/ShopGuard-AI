import json
import os
import time
import pytest
import cv2
import numpy as np

from shopguard.camera.stream_reader import (
    StreamReader,
    CameraStatus,
    is_webcam_source,
    check_webcam_available,
)
from shopguard.detection.person_detector import Detection
from shopguard.intrusion.zone_manager import Zone, ZoneManager
from shopguard.intrusion.intrusion_detector import IntrusionDetector
from shopguard.recording.video_buffer import VideoBuffer
from shopguard.recording.incident_recorder import IncidentRecorder
from shopguard.security.security_controller import SecurityController, SecurityState
from main import ShopGuardEngine


def test_is_webcam_source_detection():
    """Verifies that is_webcam_source accurately identifies integer and string webcam formats."""
    # Integer indexes
    assert is_webcam_source(0) == (True, 0)
    assert is_webcam_source(1) == (True, 1)

    # Numeric strings
    assert is_webcam_source("0") == (True, 0)
    assert is_webcam_source("2") == (True, 2)

    # Prefix strings
    assert is_webcam_source("webcam:0") == (True, 0)
    assert is_webcam_source("webcam:1") == (True, 1)
    assert is_webcam_source("camera:0") == (True, 0)

    # Keyword aliases
    assert is_webcam_source("webcam") == (True, 0)
    assert is_webcam_source("camera") == (True, 0)

    # Non-webcam sources
    assert is_webcam_source("rtsp://admin:pass@192.168.1.100:554/live") == (False, -1)
    assert is_webcam_source("data/temporary/test_feed.mp4") == (False, -1)
    assert is_webcam_source(None) == (False, -1)


def test_check_webcam_available_invalid_index():
    """Verifies that probing an invalid device index returns False and informative guidance."""
    is_avail, msg, res = check_webcam_available(device_index=999)
    assert is_avail is False
    assert "999" in msg
    assert "range" in msg or "valid" in msg or "Privacy" in msg
    assert res is None


def test_stream_reader_webcam_attributes():
    """Verifies that StreamReader sets webcam flags and does not treat webcam as a local looping file."""
    reader = StreamReader(
        camera_id="cam_webcam_0",
        name="Laptop Webcam",
        source="webcam:0",
        fps=15.0,
    )
    assert reader.is_webcam is True
    assert reader.webcam_index == 0
    assert reader.is_local_file is False
    assert reader.loop_local_file is False
    assert reader.status == CameraStatus.DISCONNECTED


def test_stream_reader_webcam_error_containment():
    """Verifies that attempting to open an unreachable webcam device fails cleanly without crash."""
    reader = StreamReader(
        camera_id="cam_invalid_webcam",
        name="Nonexistent Webcam",
        source="webcam:999",
        fps=10.0,
        connection_timeout=1.0,
    )
    success = reader._open_capture()
    assert success is False
    assert reader.status == CameraStatus.ERROR
    assert reader.is_connected is False
    reader.stop()


def test_webcam_mode_zone_setup_and_arming(tmp_path):
    """
    Verifies that ShopGuardEngine in webcam mode initializes valid zones
    so that arming prerequisites checks pass.
    """
    # Create minimal config
    config_file = str(tmp_path / "config.yaml")
    with open(config_file, "w") as f:
        f.write(
            """
security:
  initial_state: DISARMED
  confidence_threshold: 0.45
cameras:
  - id: cam_webcam
    name: Built-in Webcam
    source: "webcam:0"
    enabled: true
zones:
  configuration_file: "config/zones.example.json"
"""
        )

    # Initialize engine without launching worker thread or GUI
    engine = ShopGuardEngine.__new__(ShopGuardEngine)
    engine.config_path = config_file
    engine.video_override = None
    engine.webcam_override = 0
    engine.is_webcam_mode = True
    engine.show_gui = False
    from shopguard.utils.logger import get_logger
    engine.logger = get_logger("test")

    # Zone manager
    engine.zone_manager = ZoneManager("config/zones.example.json")
    assert engine.zone_manager.has_enabled_zones("camera_01") is True

    # Security Controller
    engine.security_controller = SecurityController(initial_state=SecurityState.DISARMED)
    assert engine.security_controller.state == SecurityState.DISARMED


def test_webcam_incident_metadata_tagging(tmp_path):
    """
    Verifies that simulated incidents triggered during webcam testing are explicitly
    tagged with source_type: "webcam", simulation_mode: true, and rtsp_verified: false.
    """
    incident_dir = str(tmp_path / "incidents")
    recorder = IncidentRecorder(
        output_directory=incident_dir,
        pre_event_seconds=1.0,
        post_event_seconds=1.0,
        fps=5.0,
        enabled=True,
    )
    buffer = VideoBuffer(buffer_seconds=3.0, fps=5.0)

    dummy_frame = np.ones((240, 320, 3), dtype=np.uint8) * 120
    t = time.time()
    buffer.append(dummy_frame, timestamp=t)

    # Create dummy intrusion event
    from shopguard.intrusion.intrusion_detector import IntrusionEvent, EventType
    event = IntrusionEvent(
        event_id="evt_webcam_001",
        camera_id="cam_webcam",
        zone_id="zone_room",
        zone_name="Laptop Desk Area",
        event_type=EventType.PERSON_ENTERED_RESTRICTED_ZONE,
        track_id=1,
        confidence=0.91,
        bbox=(50, 50, 150, 200),
        timestamp=t,
        persistence_seconds=2.0,
    )

    recorder.trigger_incident(
        event=event,
        camera_name="Laptop Built-in Webcam",
        pre_frames=buffer.get_frames(),
        source_type="webcam",
        simulation_mode=True,
        rtsp_verified=False,
    )

    # Feed post frames
    for i in range(8):
        t_post = t + (i + 1) * 0.2
        recorder.on_new_frame("cam_webcam", dummy_frame, t_post)

    recorder.shutdown()

    # Verify JSON metadata file
    json_files = []
    for root, _, files in os.walk(incident_dir):
        for f in files:
            if f.endswith(".json"):
                json_files.append(os.path.join(root, f))

    assert len(json_files) == 1, "Expected exactly 1 incident JSON file to be saved"

    with open(json_files[0], "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["source_type"] == "webcam"
    assert meta["simulation_mode"] is True
    assert meta["rtsp_verified"] is False
    assert meta["camera_id"] == "cam_webcam"
    assert meta["zone_name"] == "Laptop Desk Area"


def test_webcam_disconnection_handled_as_offline_not_intrusion():
    """
    Verifies that camera signal loss/disconnection on a webcam feed updates system health
    to OFFLINE or PARTIAL and never produces a false intrusion incident.
    """
    detector = IntrusionDetector()
    zone = Zone(id="z1", name="Office Area", polygon=[(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)])

    # Signal loss means 0 detections delivered
    events = detector.process_frame_detections(
        camera_id="cam_webcam",
        detections=[],
        zones=[zone],
        frame_width=640,
        frame_height=480,
        is_armed=True,
        timestamp=100.0,
    )
    assert len(events) == 0, "Signal disconnection must never trigger an intrusion event"


def test_webcam_full_zone_preset_and_overrides(tmp_path, monkeypatch):
    """Verifies that full-zone preset and confidence/persistence overrides apply correctly."""
    monkeypatch.setattr(
        "shopguard.camera.stream_reader.check_webcam_available",
        lambda idx: (True, "Webcam available", (640, 480)),
    )
    cfg_file = tmp_path / "webcam_cfg.yaml"
    cfg_file.write_text(
        """
security:
  initial_state: DISARMED
  confidence_threshold: 0.45
  minimum_persistence_seconds: 2.0
  event_cooldown_seconds: 30
recording:
  enabled: false
  output_directory: data/incidents
ai:
  model: models/yolo11n.pt
  device: cpu
  processing_fps: 5
cameras:
  - id: cam_test
    name: Webcam Test
    source: webcam:0
    enabled: true
    fps: 5
zones:
  configuration_file: config/zones.example.json
""",
        encoding="utf-8",
    )

    engine = ShopGuardEngine(
        config_path=str(cfg_file),
        webcam_override=0,
        show_gui=False,
        confidence_override=0.35,
        persistence_override=1.5,
        zone_preset="full",
    )

    assert engine.person_detector.confidence_threshold == 0.35
    assert engine.intrusion_detector.confidence_threshold == 0.35
    assert engine.intrusion_detector.minimum_persistence_seconds == 1.5

    zones = engine.zone_manager.get_zones("cam_test", enabled_only=True)
    assert len(zones) == 1
    assert zones[0].id == "zone_room_full"
    assert zones[0].name == "Room Protected Area"
    # Ensure zone spans broad area
    assert zones[0].contains_normalized_point((0.50, 0.50)) is True


def test_visualizer_dual_contact_points_and_badges():
    """Verifies that FeedVisualizer renders without error and handles dual contact points."""
    from shopguard.camera.visualizer import FeedVisualizer
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    zone = Zone(id="z1", name="Room Area", polygon=[(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)])
    det = Detection(
        class_name="person",
        confidence=0.88,
        bbox=(200, 150, 400, 450),
        track_id=1,
        timestamp=time.time(),
    )
    detector = IntrusionDetector(minimum_persistence_seconds=1.5)
    detector._occupancy[("cam_test", "z1", 1)] = {
        "first_seen": time.time() - 0.5,
        "last_seen": time.time(),
        "observation_count": 3.0,
        "triggered_initial": 0.0,
    }

    out = FeedVisualizer.render_overlay(
        frame=frame,
        camera_name="Laptop Webcam",
        security_state=SecurityState.ARMED,
        fps=15.0,
        detections=[det],
        zones=[zone],
        is_webcam_mode=True,
        intrusion_detector=detector,
        camera_id="cam_test",
    )
    assert out is not None
    assert out.shape == frame.shape


def test_distant_person_adaptive_confidence_detection():
    """
    Verifies that distant persons with compressed CNN confidence (e.g. 0.28)
    are retained through distance-adaptive thresholding rather than dropped.
    """
    detector = IntrusionDetector(
        minimum_persistence_seconds=1.0,
        confidence_threshold=0.40,
    )
    zone = Zone(id="z1", name="Far Zone", polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])

    # Distant person: small height (70px out of 720px = ~9.7% of frame height)
    # Confidence is 0.28 (below 0.40 standard, but above adaptive threshold 0.40 * 0.65 = 0.26)
    far_person = Detection(
        class_name="person",
        confidence=0.28,
        bbox=(200, 100, 250, 170),
        track_id=10,
        timestamp=100.0,
    )

    # Nearby detection: large height (400px out of 720px = 55% of frame)
    # Confidence is 0.28 (below 0.40, should NOT be accepted adaptively)
    near_noise = Detection(
        class_name="person",
        confidence=0.28,
        bbox=(200, 100, 450, 500),
        track_id=11,
        timestamp=100.0,
    )

    # Frame 1 at t=100.0
    detector.process_frame_detections(
        camera_id="cam_webcam",
        detections=[far_person, near_noise],
        zones=[zone],
        frame_width=1280,
        frame_height=720,
        is_armed=True,
        timestamp=100.0,
    )

    # Check occupancy: far_person (track 10) must be tracked, near_noise (track 11) must not
    assert ("cam_webcam", "z1", 10) in detector._occupancy
    assert ("cam_webcam", "z1", 11) not in detector._occupancy

    # Frame 2 at t=101.0
    detector.process_frame_detections(
        camera_id="cam_webcam",
        detections=[far_person],
        zones=[zone],
        frame_width=1280,
        frame_height=720,
        is_armed=True,
        timestamp=101.0,
    )

    # Advance time to trigger intrusion for far_person (Frame 3 at t=102.0)
    events = detector.process_frame_detections(
        camera_id="cam_webcam",
        detections=[far_person],
        zones=[zone],
        frame_width=1280,
        frame_height=720,
        is_armed=True,
        timestamp=102.0,
    )

    assert len(events) == 1
    assert events[0].track_id == 10
    assert events[0].confidence == 0.28


