"""
ShopGuard AI - Phase 2 Local Security Agent Automated Test Suite
Verifies:
1. All REST API endpoints (/api/status, /api/cameras, /api/security/state,
   /api/security/arm, /api/security/disarm, /api/incidents, /api/incidents/{id},
   /api/health, /api/system/info).
2. Strict authentication enforcement (X-API-Key and Bearer token).
3. Unauthorized access rejection (HTTP 401).
4. State validation and duplicate operation prevention (HTTP 409).
5. Safe startup in DISARMED mode and crash recovery auditing.
6. Camera health tracking (disconnection handled as health degradation, never intrusion).
7. RTSP credential masking in all API responses.
8. Incident retrieval, pagination, and path-traversal protection.
"""

import json
import os
import threading
import time
import pytest
import numpy as np
from fastapi.testclient import TestClient

from shopguard.agent.server import create_app
from shopguard.agent.security_auth import AgentAuthManager, auth_manager
from shopguard.agent.state_store import PersistentStateStore
from shopguard.camera.camera_manager import CameraManager
from shopguard.camera.stream_reader import CameraStatus, StreamReader
from shopguard.intrusion.zone_manager import Zone, ZoneManager
from shopguard.security.security_controller import SecurityController, SecurityState
from shopguard.monitoring.health_monitor import HealthMonitor
from shopguard.recording.incident_recorder import IncidentRecorder


class MockEngine:
    """Mock ShopGuardEngine for deterministic, lightning-fast API testing."""

    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.incidents_dir = str(tmp_path / "incidents")
        os.makedirs(self.incidents_dir, exist_ok=True)

        self.security_controller = SecurityController(initial_state=SecurityState.DISARMED)
        self.camera_manager = CameraManager()
        self.zone_manager = ZoneManager("config/zones.example.json")

        # Mock person detector
        class MockDetector:
            is_loaded = True
            model_path = "models/yolo11n.pt"
            device = "cpu"
            confidence_threshold = 0.45
            def get_diagnostics(self):
                return None

        self.person_detector = MockDetector()

        # Add a simulated mock camera
        self.mock_reader = StreamReader(
            camera_id="cam_main",
            name="Front Door Camera",
            source="rtsp://admin:SecretPass123@192.168.1.100:554/live",
            fps=15.0,
        )
        self.mock_reader._status = CameraStatus.CONNECTED
        self.mock_reader._last_successful_read_time = time.time()
        self.mock_reader._last_frame = np.zeros((2, 2, 3), dtype=np.uint8)
        self.mock_reader._last_frame_time = time.time()
        self.mock_reader._running = True
        self.mock_reader._thread = threading.current_thread()
        self.camera_manager._cameras["cam_main"] = self.mock_reader

        # Add mock zone
        self.zone_manager.set_zones(
            "cam_main",
            [Zone(id="z1", name="Entrance Area", polygon=[(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)], enabled=True)]
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

        self.is_running = True
        self.readiness_waits = []

    def start(self):
        self.is_running = True

    def stop_monitoring(self):
        self.is_running = False

    def stop(self):
        self.is_running = False

    def wait_until_monitoring_ready(self, timeout_seconds):
        self.readiness_waits.append(timeout_seconds)
        return True


@pytest.fixture
def test_setup(tmp_path):
    """Initializes a mock engine and FastAPI test client with state store."""
    engine = MockEngine(tmp_path)
    state_file = str(tmp_path / "test_state.json")
    app = create_app(engine=engine, state_file=state_file)
    client = TestClient(app)
    valid_key = auth_manager.api_key
    return {
        "engine": engine,
        "client": client,
        "api_key": valid_key,
        "tmp_path": tmp_path,
        "state_file": state_file,
    }


def test_status_endpoint_initial_state(test_setup):
    """Verifies that GET /api/status returns RUNNING service and safe DISARMED state."""
    client = test_setup["client"]
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert data["service_status"] == "RUNNING"
    assert data["security_state"] == "DISARMED"
    assert data["is_armed"] is False
    assert data["cameras_total"] == 1
    assert data["cameras_connected"] == 1
    assert data["uptime_seconds"] >= 0.0


def test_cameras_endpoint_masks_credentials(test_setup):
    """Verifies that GET /api/cameras NEVER leaks RTSP passwords."""
    client = test_setup["client"]
    res = client.get("/api/cameras")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["connected"] == 1

    cam = data["cameras"][0]
    assert cam["id"] == "cam_main"
    assert cam["name"] == "Front Door Camera"
    assert "SecretPass123" not in cam["source_masked"]
    assert "***" in cam["source_masked"]
    assert cam["is_connected"] is True


def test_security_state_endpoint(test_setup):
    """Verifies that GET /api/security/state reports readiness and zone count."""
    client = test_setup["client"]
    res = client.get("/api/security/state")
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "DISARMED"
    assert data["is_armed"] is False
    assert data["can_arm"] is True
    assert data["active_zones_count"] >= 1
    assert data["connected_cameras"] == 1


def test_control_endpoints_require_authentication(test_setup):
    """Verifies that POST /api/security/arm and disarm reject unauthenticated requests."""
    client = test_setup["client"]

    # 1. No auth headers -> 401 Unauthorized
    arm_res = client.post("/api/security/arm", json={"reason": "Unauthorized test"})
    assert arm_res.status_code == 401
    assert arm_res.json()["detail"]["error"] == "UNAUTHORIZED"

    disarm_res = client.post("/api/security/disarm", json={"reason": "Unauthorized test"})
    assert disarm_res.status_code == 401

    # 2. Invalid auth key -> 401 Unauthorized
    bad_arm = client.post(
        "/api/security/arm",
        headers={"X-API-Key": "completely_wrong_key"},
        json={"reason": "Bad key test"},
    )
    assert bad_arm.status_code == 401


def test_control_endpoints_accept_allowlisted_tailscale_identity(test_setup, monkeypatch):
    """Tailscale Serve identities are authorized only when explicitly allowlisted."""
    client = test_setup["client"]
    monkeypatch.setattr(auth_manager, "_tailscale_users", {"shopkeeper@example.com"})

    denied = client.post(
        "/api/security/arm",
        headers={"Tailscale-User-Login": "other@example.com"},
        json={"reason": "Not allowlisted"},
    )
    assert denied.status_code == 401

    headers = {"Tailscale-User-Login": "ShopKeeper@Example.com"}
    arm_res = client.post(
        "/api/security/arm", headers=headers, json={"reason": "Shopkeeper armed"}
    )
    assert arm_res.status_code == 200
    assert arm_res.json()["state"] == "ARMED"

    disarm_res = client.post(
        "/api/security/disarm", headers=headers, json={"reason": "Shopkeeper disarmed"}
    )
    assert disarm_res.status_code == 200
    assert disarm_res.json()["state"] == "DISARMED"


def test_tailscale_allowlist_reads_utf8_bom(tmp_path):
    """Windows PowerShell UTF-8 output must not corrupt the first allowed login."""
    allowlist = tmp_path / "tailscale_allowed_users.txt"
    allowlist.write_text("\ufeffshopkeeper@example.com\n", encoding="utf-8")
    manager = AgentAuthManager(
        secret_path=str(tmp_path / "agent_api_key.secret"),
        tailscale_users_path=str(allowlist),
    )
    assert manager.validate_tailscale_user("ShopKeeper@Example.com")
    assert not manager.validate_tailscale_user("other@example.com")


def test_arm_and_disarm_lifecycle_with_x_api_key(test_setup):
    """Verifies authorized arm and disarm lifecycle using X-API-Key header."""
    client = test_setup["client"]
    api_key = test_setup["api_key"]
    engine = test_setup["engine"]
    headers = {"X-API-Key": api_key}

    # 1. Arm system
    arm_res = client.post("/api/security/arm", headers=headers, json={"reason": "Night security activation"})
    assert arm_res.status_code == 200
    arm_data = arm_res.json()
    assert arm_data["success"] is True
    assert arm_data["state"] == "ARMED"
    assert engine.security_controller.state == SecurityState.ARMED
    assert engine.is_running is True
    assert engine.readiness_waits

    # 2. Duplicate arm attempt -> 409 Conflict
    dup_arm = client.post("/api/security/arm", headers=headers, json={"reason": "Repeat arm"})
    assert dup_arm.status_code == 409
    assert dup_arm.json()["detail"]["error"] == "ALREADY_ARMED"

    # 3. Disarm system
    disarm_res = client.post("/api/security/disarm", headers=headers, json={"reason": "Morning shop opening"})
    assert disarm_res.status_code == 200
    disarm_data = disarm_res.json()
    assert disarm_data["success"] is True
    assert disarm_data["state"] == "DISARMED"
    assert engine.security_controller.state == SecurityState.DISARMED
    assert engine.is_running is False
    assert client.get("/api/status").status_code == 200

    evaluated_armed_states = []

    class EvaluationProbe:
        def process_frame_detections(self, **frame_data):
            evaluated_armed_states.append(frame_data["is_armed"])
            return []

    engine.security_controller.evaluate_intrusions(
        EvaluationProbe(),
        camera_id="cam_main",
        detections=[],
        zones=[],
        frame_width=2,
        frame_height=2,
        timestamp=time.time(),
    )
    assert evaluated_armed_states == [False]

    # 4. Duplicate disarm attempt -> 409 Conflict
    dup_disarm = client.post("/api/security/disarm", headers=headers, json={"reason": "Repeat disarm"})
    assert dup_disarm.status_code == 409
    assert dup_disarm.json()["detail"]["error"] == "ALREADY_DISARMED"


def test_arm_with_bearer_authorization_header(test_setup):
    """Verifies that Authorization: Bearer <key> is accepted for control operations."""
    client = test_setup["client"]
    api_key = test_setup["api_key"]
    headers = {"Authorization": f"Bearer {api_key}"}

    arm_res = client.post("/api/security/arm", headers=headers, json={"reason": "Bearer auth test"})
    assert arm_res.status_code == 200
    assert arm_res.json()["state"] == "ARMED"

    disarm_res = client.post("/api/security/disarm", headers=headers)
    assert disarm_res.status_code == 200
    assert disarm_res.json()["state"] == "DISARMED"


def test_arm_persists_across_client_disconnect(test_setup):
    """
    Verifies that arming persists when a mobile client disconnects, closes,
    or a new client connects. System must remain ARMED until explicit disarm.
    """
    client = test_setup["client"]
    api_key = test_setup["api_key"]
    headers = {"X-API-Key": api_key}
    app = client.app

    # 1. Arm system from first client
    arm_res = client.post("/api/security/arm", headers=headers, json={"reason": "Mobile client 1 arm"})
    assert arm_res.status_code == 200
    assert arm_res.json()["state"] == "ARMED"

    # 2. Simulate client disconnection / app closure by closing and discarding client
    client.close()
    del client

    # 3. Create a brand new client connection (simulating reopening app or second device)
    new_client = TestClient(app)
    state_res = new_client.get("/api/security/state")
    assert state_res.status_code == 200
    state_data = state_res.json()
    assert state_data["state"] == "ARMED", "Backend must remain ARMED across client disconnect/reconnect"
    assert state_data["is_armed"] is True

    # 4. GET /api/status also reports ARMED
    status_res = new_client.get("/api/status")
    assert status_res.status_code == 200
    assert status_res.json()["security_state"] == "ARMED"
    assert status_res.json()["is_armed"] is True

    # 5. Only explicit disarm transitions back to DISARMED
    disarm_res = new_client.post("/api/security/disarm", headers=headers, json={"reason": "Explicit mobile disarm"})
    assert disarm_res.status_code == 200
    assert disarm_res.json()["state"] == "DISARMED"

    final_state = new_client.get("/api/security/state")
    assert final_state.status_code == 200
    assert final_state.json()["state"] == "DISARMED"
    new_client.close()


def test_arm_rejected_when_prerequisites_fail(test_setup):
    """Verifies that arming is rejected (HTTP 400) when prerequisites fail and state remains DISARMED."""
    client = test_setup["client"]
    api_key = test_setup["api_key"]
    engine = test_setup["engine"]
    headers = {"X-API-Key": api_key}

    # Simulate camera disconnected before arming
    engine.mock_reader._status = CameraStatus.DISCONNECTED

    # Attempt to arm -> should be rejected with 400
    arm_res = client.post("/api/security/arm", headers=headers, json={"reason": "Fail arm attempt"})
    assert arm_res.status_code == 400
    err_data = arm_res.json()["detail"]
    assert err_data["error"] == "ARMING_REJECTED"
    assert "reasons" in err_data
    assert len(err_data["reasons"]) >= 1

    # Verify /api/security/state confirms system remains strictly DISARMED
    state_res = client.get("/api/security/state")
    assert state_res.status_code == 200
    assert state_res.json()["state"] == "DISARMED"
    assert state_res.json()["is_armed"] is False

    # Restore camera
    engine.mock_reader._status = CameraStatus.CONNECTED


def test_arm_requires_every_enabled_camera_to_have_a_fresh_frame(test_setup):
    """A connected status alone is not sufficient readiness for an ARM response."""
    client = test_setup["client"]
    engine = test_setup["engine"]
    headers = {"X-API-Key": test_setup["api_key"]}

    reader = StreamReader(
        camera_id="cam_side",
        name="Side Door Camera",
        source="rtsp://192.168.1.101/live",
    )
    reader._status = CameraStatus.CONNECTED
    reader._running = True
    reader._thread = threading.current_thread()
    engine.camera_manager._cameras["cam_side"] = reader
    engine.zone_manager.set_zones(
        "cam_side",
        [Zone(id="z2", name="Side Door", polygon=[(0.1, 0.1), (0.9, 0.1), (0.9, 0.9)], enabled=True)],
    )

    response = client.post("/api/security/arm", headers=headers, json={"reason": "Readiness test"})
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "ARMING_REJECTED"
    assert any("All enabled cameras" in reason and "cam_side" in reason for reason in detail["reasons"])
    assert engine.security_controller.state == SecurityState.DISARMED


def test_camera_disconnection_updates_health_without_intrusion(test_setup):
    """
    Verifies that camera disconnection transitions system to PARTIAL/OFFLINE
    and NEVER creates a false intrusion event.
    """
    client = test_setup["client"]
    api_key = test_setup["api_key"]
    engine = test_setup["engine"]
    headers = {"X-API-Key": api_key}

    # Arm system
    client.post("/api/security/arm", headers=headers)
    assert engine.security_controller.state == SecurityState.ARMED

    # Simulate camera disconnection
    engine.mock_reader._status = CameraStatus.DISCONNECTED
    engine.security_controller.update_camera_health()

    # State must become PARTIAL or OFFLINE, never intrusion
    assert engine.security_controller.state in (SecurityState.PARTIAL, SecurityState.OFFLINE)

    # Health endpoint reflects degradation
    health_res = client.get("/api/health")
    assert health_res.status_code == 200
    h_data = health_res.json()
    assert h_data["healthy"] is False
    assert h_data["overall_health"] in ("DEGRADED", "CRITICAL")
    assert h_data["cameras"][0]["is_connected"] is False

    # Cleanup: disarm
    client.post("/api/security/disarm", headers=headers)


def test_incidents_list_and_detail_endpoints(test_setup):
    """Verifies retrieving incident history, pagination, and single incident details."""
    client = test_setup["client"]
    tmp_path = test_setup["tmp_path"]
    incidents_dir = tmp_path / "incidents"

    # Create 2 mock incident records on disk
    inc1 = {
        "incident_id": "incident_20261105_001",
        "camera_id": "cam_main",
        "camera_name": "Front Door",
        "event_type": "PERSON_ENTERED_RESTRICTED_ZONE",
        "event_timestamp": "2026-11-05T20:00:00Z",
        "confidence": 0.88,
        "zone_id": "z1",
        "zone_name": "Entrance Area",
        "video_filename": "incident_20261105_001.mp4",
        "duration_seconds": 15.0,
        "total_frames": 75,
        "review_status": "UNREVIEWED",
    }
    (incidents_dir / "incident_20261105_001.json").write_text(json.dumps(inc1), encoding="utf-8")
    (incidents_dir / "incident_20261105_001.mp4").write_bytes(b"dummy video data")

    inc2 = {
        "incident_id": "incident_20261105_002",
        "camera_id": "cam_secondary",
        "camera_name": "Side Door",
        "event_type": "PERSON_PRESENT_IN_RESTRICTED_ZONE",
        "event_timestamp": "2026-11-05T21:00:00Z",
        "confidence": 0.76,
        "zone_id": "z2",
        "zone_name": "Back Area",
        "video_filename": "incident_20261105_002.mp4",
        "duration_seconds": 10.0,
        "total_frames": 50,
        "review_status": "UNREVIEWED",
    }
    (incidents_dir / "incident_20261105_002.json").write_text(json.dumps(inc2), encoding="utf-8")

    # 1. List all incidents
    list_res = client.get("/api/incidents")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] == 2
    assert len(list_data["incidents"]) == 2

    # 2. Filter by camera_id
    filter_res = client.get("/api/incidents?camera_id=cam_main")
    assert filter_res.status_code == 200
    assert filter_res.json()["total"] == 1
    assert filter_res.json()["incidents"][0]["incident_id"] == "incident_20261105_001"

    # 3. Retrieve valid single incident
    detail_res = client.get("/api/incidents/incident_20261105_001")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["incident_id"] == "incident_20261105_001"
    assert detail_data["video_exists"] is True
    assert detail_data["video_size_bytes"] > 0

    # 4. Non-existent incident -> 404
    missing_res = client.get("/api/incidents/incident_non_existent")
    assert missing_res.status_code == 404
    assert missing_res.json()["detail"]["error"] == "INCIDENT_NOT_FOUND"

    # 5. Path traversal attack attempt -> 400 Bad Request
    traversal_res = client.get("/api/incidents/../../etc/passwd")
    assert traversal_res.status_code in (400, 404)


def test_system_info_endpoint(test_setup):
    """Verifies that GET /api/system/info returns host environment diagnostics."""
    client = test_setup["client"]
    res = client.get("/api/system/info")
    assert res.status_code == 200
    data = res.json()
    assert data["service_name"] == "ShopGuard AI Local Security Agent"
    assert "Windows" in data["operating_system"] or len(data["operating_system"]) > 0
    assert data["cpu_count"] >= 1
    assert data["uptime_seconds"] >= 0.0
    assert data["auth_enabled"] is True


def test_persistent_state_store_and_crash_recovery(tmp_path):
    """
    Verifies that PersistentStateStore tracks transitions, flags unclean shutdowns,
    and guarantees safe DISARMED default initialization on startup.
    """
    state_file = tmp_path / "state_audit.json"

    # Session 1: Transition to ARMED, then crash (no clean shutdown)
    store1 = PersistentStateStore(file_path=str(state_file))
    store1.record_transition(SecurityState.ARMED, reason="Night arm")
    assert store1.get_state_summary()["state"] == "ARMED"
    assert store1.get_state_summary()["clean_shutdown"] is False

    # Session 2: Fresh process start after crash
    store2 = PersistentStateStore(file_path=str(state_file))
    # Must audit unclean shutdown
    assert store2.last_clean_shutdown is False
    assert store2.previous_unclean_state == "ARMED"
    # Must guarantee safe startup in DISARMED mode
    assert store2.get_state_summary()["state"] == "DISARMED"

    # Session 2 clean exit
    store2.record_clean_shutdown(SecurityState.DISARMED)
    assert store2.get_state_summary()["clean_shutdown"] is True


def test_agent_startup_forces_disarmed_and_runs_engine(tmp_path):
    """The API lifecycle starts the engine but never restores an armed state."""
    engine = MockEngine(tmp_path)
    engine.security_controller.arm()
    assert engine.security_controller.state == SecurityState.ARMED

    app = create_app(
        engine=engine,
        state_file=str(tmp_path / "safe_startup_state.json"),
    )
    with TestClient(app) as client:
        assert client.get("/api/security/state").json()["state"] == "DISARMED"
        assert engine.is_running is False

    assert engine.security_controller.state == SecurityState.DISARMED
    assert engine.is_running is False


def test_agent_factory_refuses_non_loopback_host(tmp_path):
    config_file = tmp_path / "public_agent.yaml"
    config_file.write_text(
        'security:\n  confidence_threshold: 0.5\n'
        'recording: {}\nai: {}\n'
        'cameras:\n  - id: cam_1\n    source: rtsp://127.0.0.1/live\n'
        'agent:\n  host: "0.0.0.0"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not a loopback"):
        create_app(
            config_path=str(config_file),
            state_file=str(tmp_path / "public_agent_state.json"),
        )
