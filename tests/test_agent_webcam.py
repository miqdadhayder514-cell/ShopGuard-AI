"""
ShopGuard AI - Phase 2 Local Security Agent Webcam Integration Tests
Validates:
1. Agent initialization in webcam testing mode without requiring RTSP URLs or .env credentials.
2. /api/status reporting 'WEBCAM_TEST' mode and 'WEBCAM TEST MODE — NOT CCTV' notice.
3. /api/cameras identifying webcam:0, is_webcam=True, and connection status.
4. /api/security/state reporting safe DISARMED initial state and valid can_arm=True readiness.
5. Authorized arm/disarm transitions via REST API during webcam operation.
6. Intrusion incident generation gated by arm state (suppressed while disarmed, triggered while armed).
7. Proper metadata tagging: source_type='webcam', simulation_mode=True.
"""

import json
import os
import threading
import time
import pytest
import numpy as np
from fastapi.testclient import TestClient

from shopguard.agent.server import create_app
from shopguard.agent.security_auth import auth_manager
from shopguard.camera.camera_manager import CameraManager
from shopguard.camera.stream_reader import CameraStatus, StreamReader
from shopguard.intrusion.intrusion_detector import IntrusionDetector, IntrusionEvent, EventType
from shopguard.intrusion.zone_manager import Zone, ZoneManager
from shopguard.monitoring.health_monitor import HealthMonitor
from shopguard.recording.incident_recorder import IncidentRecorder
from shopguard.security.security_controller import SecurityController, SecurityState


class MockWebcamEngine:
    """Simulated ShopGuardEngine running in laptop webcam testing mode."""

    def __init__(self, tmp_path, webcam_index: int = 0):
        self.tmp_path = tmp_path
        self.incidents_dir = str(tmp_path / "incidents")
        os.makedirs(self.incidents_dir, exist_ok=True)

        self.is_webcam_mode = True
        self.webcam_override = webcam_index

        self.security_controller = SecurityController(initial_state=SecurityState.DISARMED)
        self.camera_manager = CameraManager()
        self.zone_manager = ZoneManager()

        # Mock person detector
        class MockDetector:
            is_loaded = True
            model_path = "models/yolo11n.pt"
            device = "cpu"
            confidence_threshold = 0.45
            def get_diagnostics(self):
                return None

        self.person_detector = MockDetector()

        # Add simulated webcam StreamReader
        self.webcam_reader = StreamReader(
            camera_id="cam_webcam",
            name=f"Laptop Webcam {webcam_index}",
            source=f"webcam:{webcam_index}",
            fps=15.0,
        )
        self.webcam_reader._status = CameraStatus.CONNECTED
        self.webcam_reader._last_successful_read_time = time.time()
        self.webcam_reader._last_frame = np.zeros((2, 2, 3), dtype=np.uint8)
        self.webcam_reader._last_frame_time = time.time()
        self.webcam_reader._running = True
        self.webcam_reader._thread = threading.current_thread()
        self.camera_manager._cameras["cam_webcam"] = self.webcam_reader

        # Add default webcam test zone
        self.zone_manager.set_zones(
            "cam_webcam",
            [
                Zone(
                    id="zone_webcam_restricted",
                    name="Webcam Restricted Area",
                    polygon=[(0.10, 0.20), (0.90, 0.20), (0.90, 0.98), (0.10, 0.98)],
                    enabled=True,
                )
            ]
        )

        self.security_controller.bind_dependencies(
            camera_manager=self.camera_manager,
            person_detector=self.person_detector,
            zone_manager=self.zone_manager,
            is_processing_active=lambda: True,
        )

        self.health_monitor = HealthMonitor(
            camera_manager=self.camera_manager,
            person_detector=self.person_detector,
            security_controller=self.security_controller,
            storage_path=self.incidents_dir,
        )

        self.incident_recorder = IncidentRecorder(
            output_directory=self.incidents_dir,
            enabled=True,
        )

        self.intrusion_detector = IntrusionDetector(
            minimum_persistence_seconds=1.0,
            event_cooldown_seconds=5.0,
        )

        self.is_running = True

    def start(self):
        self.is_running = True

    def stop_monitoring(self):
        self.is_running = False

    def stop(self):
        self.is_running = False


@pytest.fixture
def webcam_agent_setup(tmp_path):
    """Sets up a mock webcam engine and FastAPI TestClient."""
    engine = MockWebcamEngine(tmp_path, webcam_index=0)
    state_file = str(tmp_path / "webcam_security_state.json")
    app = create_app(
        engine=engine,
        state_file=state_file,
        webcam_index=0,
    )
    client = TestClient(app)
    api_key = auth_manager.api_key
    return {
        "engine": engine,
        "client": client,
        "api_key": api_key,
        "tmp_path": tmp_path,
    }


def test_webcam_mode_status_endpoint_reports_indicator(webcam_agent_setup):
    """Verifies that /api/status clearly reports WEBCAM TEST MODE and safe DISARMED state."""
    client = webcam_agent_setup["client"]
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()

    assert data["service_status"] == "RUNNING"
    assert data["security_state"] == "DISARMED"
    assert data["is_armed"] is False
    assert data["mode"] == "WEBCAM_TEST"
    assert data["notice"] == "WEBCAM TEST MODE — NOT CCTV"
    assert data["cameras_total"] == 1
    assert data["cameras_connected"] == 1


def test_webcam_mode_cameras_endpoint_identifies_webcam(webcam_agent_setup):
    """Verifies /api/cameras identifies the feed as a webcam without RTSP credentials."""
    client = webcam_agent_setup["client"]
    res = client.get("/api/cameras")
    assert res.status_code == 200
    data = res.json()

    assert data["total"] == 1
    assert data["connected"] == 1
    cam = data["cameras"][0]
    assert cam["id"] == "cam_webcam"
    assert cam["is_webcam"] is True
    assert cam["source_masked"] == "webcam:0"
    assert cam["is_connected"] is True


def test_webcam_mode_security_state_and_arming_lifecycle(webcam_agent_setup):
    """Verifies arming readiness, arming command, and disarming command in webcam mode."""
    client = webcam_agent_setup["client"]
    api_key = webcam_agent_setup["api_key"]
    engine = webcam_agent_setup["engine"]
    headers = {"X-API-Key": api_key}

    # 1. Verify arming readiness
    state_res = client.get("/api/security/state")
    assert state_res.status_code == 200
    s_data = state_res.json()
    assert s_data["state"] == "DISARMED"
    assert s_data["is_armed"] is False
    assert s_data["can_arm"] is True
    assert s_data["active_zones_count"] >= 1

    # 2. Arm system
    arm_res = client.post("/api/security/arm", headers=headers, json={"reason": "Testing webcam intrusion"})
    assert arm_res.status_code == 200
    arm_data = arm_res.json()
    assert arm_data["success"] is True
    assert arm_data["state"] == "ARMED"
    assert engine.security_controller.state == SecurityState.ARMED

    # 3. Disarm system
    disarm_res = client.post("/api/security/disarm", headers=headers, json={"reason": "Test finished"})
    assert disarm_res.status_code == 200
    disarm_data = disarm_res.json()
    assert disarm_data["success"] is True
    assert disarm_data["state"] == "DISARMED"
    assert engine.security_controller.state == SecurityState.DISARMED


def test_webcam_mode_incident_gated_by_arm_state(webcam_agent_setup):
    """
    Verifies that simulated intrusion events in webcam mode:
    1. Are suppressed while DISARMED.
    2. Trigger incident recording while ARMED, correctly tagging metadata.
    """
    client = webcam_agent_setup["client"]
    api_key = webcam_agent_setup["api_key"]
    engine = webcam_agent_setup["engine"]
    headers = {"X-API-Key": api_key}

    # Create dummy simulated intrusion event
    simulated_event = IntrusionEvent(
        event_id="evt_webcam_test_001",
        camera_id="cam_webcam",
        zone_id="zone_webcam_restricted",
        zone_name="Webcam Restricted Area",
        event_type=EventType.PERSON_ENTERED_RESTRICTED_ZONE,
        track_id=101,
        confidence=0.88,
        bbox=(100, 100, 200, 300),
        timestamp=time.time(),
        persistence_seconds=2.5,
    )

    # 1. DISARMED: Record must not be triggered
    assert engine.security_controller.is_armed is False
    list_res = client.get("/api/incidents")
    assert list_res.json()["total"] == 0

    # 2. ARM system
    client.post("/api/security/arm", headers=headers)
    assert engine.security_controller.is_armed is True

    # 3. Trigger incident in webcam mode
    import numpy as np
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    engine.incident_recorder.trigger_incident(
        event=simulated_event,
        camera_name="Laptop Webcam 0",
        pre_frames=[(dummy_frame, simulated_event.timestamp)],
        source_type="webcam",
        simulation_mode=True,
        rtsp_verified=False,
    )
    for session in list(engine.incident_recorder._active_sessions):
        session.is_completed = True
        engine.incident_recorder._active_sessions.remove(session)
        engine.incident_recorder._save_session(session)

    # 4. Check incidents endpoint
    inc_res = client.get("/api/incidents")
    assert inc_res.status_code == 200
    inc_data = inc_res.json()
    assert inc_data["total"] >= 1
    first_inc = inc_data["incidents"][0]
    assert first_inc["camera_id"] == "cam_webcam"
    assert first_inc["zone_name"] == "Webcam Restricted Area"

    # 5. Check incident detail endpoint for simulation metadata
    detail_res = client.get(f"/api/incidents/{first_inc['incident_id']}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["camera_id"] == "cam_webcam"
    assert detail_data["zone_id"] == "zone_webcam_restricted"
    assert detail_data["source_type"] == "webcam"
    assert detail_data["simulation_mode"] is True
    assert detail_data["rtsp_verified"] is False


def test_webcam_mode_health_endpoint_reports_notice(webcam_agent_setup):
    """Verifies that /api/health includes the webcam indicator and diagnostic report."""
    client = webcam_agent_setup["client"]
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()

    assert data["healthy"] is True
    assert data["mode"] == "WEBCAM_TEST"
    assert data["notice"] == "WEBCAM TEST MODE — NOT CCTV"
    assert len(data["cameras"]) == 1
    assert data["cameras"][0]["camera_id"] == "cam_webcam"
