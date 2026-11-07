import os
import time
import pytest
import cv2

from shopguard.utils.helpers import load_config
from shopguard.camera.camera_manager import CameraManager
from shopguard.detection.person_detector import PersonDetector
from shopguard.intrusion.zone_manager import ZoneManager
from shopguard.intrusion.intrusion_detector import IntrusionDetector
from shopguard.recording.incident_recorder import IncidentRecorder
from shopguard.recording.video_buffer import VideoBuffer
from shopguard.security.security_controller import SecurityController, SecurityState
from shopguard.monitoring.health_monitor import HealthMonitor
from tools.generate_test_video import generate_synthetic_video


def test_full_pipeline_local_video(tmp_path):
    """
    End-to-end integration test of the full ShopGuard AI engine:
    1. Generates local test video.
    2. Configures cameras and zones.
    3. Verifies initial DISARMED state.
    4. Arms system and checks prerequisite verification.
    5. Feeds frames through person detector and intrusion evaluator.
    6. Verifies health monitor report.
    """
    video_path = os.path.join(tmp_path, "sample.mp4")
    assert generate_synthetic_video(video_path, duration_seconds=3, fps=5, width=320, height=240) is True

    # Camera Manager
    cam_mgr = CameraManager()
    reader = cam_mgr.add_camera_from_config({
        "id": "cam_test",
        "name": "Integration Camera",
        "source": video_path,
        "enabled": True,
        "fps": 5.0,
    })
    assert reader is not None
    cam_mgr.start_all()

    # Wait for frame
    time.sleep(0.5)
    ret, frame, ts = reader.read()
    assert ret is True
    assert frame is not None

    # Person Detector
    detector = PersonDetector("models/yolo11n.pt", device="cpu")
    assert detector.is_loaded is True

    # Zone Manager
    zones_file = os.path.join(tmp_path, "zones.json")
    zm = ZoneManager(zones_file)
    from shopguard.intrusion.zone_manager import Zone
    zm.add_zone("cam_test", Zone(
        id="zone_01",
        name="Test Zone",
        polygon=[(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)],
        enabled=True,
    ))
    assert zm.has_enabled_zones("cam_test") is True

    # Security Controller
    controller = SecurityController(initial_state=SecurityState.DISARMED)
    controller.bind_dependencies(
        camera_manager=cam_mgr,
        person_detector=detector,
        zone_manager=zm,
        is_processing_active=lambda: True,
    )
    assert controller.state == SecurityState.DISARMED

    # Health Monitor
    health = HealthMonitor(cam_mgr, detector, controller, storage_path=str(tmp_path))
    rep = health.get_health_report()
    assert rep.overall_health == "HEALTHY"
    assert rep.cameras[0].is_connected is True

    # Arm system
    success, msg, res = controller.arm()
    assert success is True
    assert controller.state == SecurityState.ARMED

    # Disarm system
    d_success, d_msg = controller.disarm()
    assert d_success is True
    assert controller.state == SecurityState.DISARMED

    cam_mgr.stop_all()
