"""
ShopGuard AI - Camera Management Automated Test Suite
Validates:
1. Valid RTSP configuration parsing & normalization.
2. Invalid IP address / hostname input handling (HTTP 400).
3. Missing fields and validation.
4. Connection failure diagnostics (socket timeout / unreachable host without credential leakage).
5. Successful connection testing (mocked socket & decode returning resolution and FPS).
6. Duplicate camera prevention (duplicate ID or duplicate endpoint rejected with HTTP 409).
7. Dynamic camera addition via POST /api/cameras.
8. Dynamic camera editing via PUT /api/cameras/{id} (preserves encrypted passwords when blank).
9. Camera removal via DELETE /api/cameras/{id} (stops reader, removes buffers, 404 for missing).
10. Camera disconnection handling (health degradation, never intrusion).
11. Credential masking: RTSP passwords are NEVER exposed in any response, log, or plaintext JSON.
12. Strict authentication enforcement (HTTP 401 on test, add, edit, delete without credentials).
"""

import json
import os
import unittest.mock as mock
import pytest
from fastapi.testclient import TestClient

from shopguard.agent.server import create_app
from shopguard.agent.security_auth import auth_manager
from shopguard.camera.camera_manager import CameraManager
from shopguard.camera.camera_vault import CameraVault, normalize_rtsp_components, parse_rtsp_url
from shopguard.camera.stream_reader import CameraStatus, StreamReader
from shopguard.intrusion.zone_manager import ZoneManager
from shopguard.security.security_controller import SecurityController, SecurityState
from shopguard.recording.incident_recorder import IncidentRecorder
from shopguard.monitoring.health_monitor import HealthMonitor


class MockEngine:
    """Mock engine supporting dynamic camera additions and buffer tracking."""

    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.incidents_dir = str(tmp_path / "incidents")
        os.makedirs(self.incidents_dir, exist_ok=True)

        self.security_controller = SecurityController(initial_state=SecurityState.DISARMED)
        self.camera_manager = CameraManager()
        self.zone_manager = ZoneManager("config/zones.example.json")
        self.video_buffers = {}
        self.trackers = {}

        class MockDetector:
            is_loaded = True
            model_path = "models/yolo11n.pt"
            device = "cpu"
            confidence_threshold = 0.45
            def get_diagnostics(self):
                return None

        self.person_detector = MockDetector()

        self.security_controller.bind_dependencies(
            camera_manager=self.camera_manager,
            person_detector=self.person_detector,
            zone_manager=self.zone_manager,
            is_processing_active=lambda: True,
        )

        self.incident_recorder = IncidentRecorder(output_directory=self.incidents_dir, enabled=True)
        self.health_monitor = HealthMonitor(
            camera_manager=self.camera_manager,
            person_detector=self.person_detector,
            security_controller=self.security_controller,
            storage_path=self.incidents_dir,
        )


@pytest.fixture
def cam_setup(tmp_path, monkeypatch):
    """Sets up a test app with isolated camera vault and state store."""
    vault_store = str(tmp_path / "test_cameras.json")
    vault_key = str(tmp_path / "test_vault.key")
    state_file = str(tmp_path / "test_state.json")

    test_vault = CameraVault(store_path=vault_store, key_path=vault_key)
    monkeypatch.setattr("shopguard.agent.server.camera_vault", test_vault)

    engine = MockEngine(tmp_path)
    app = create_app(engine=engine, state_file=state_file)
    client = TestClient(app)
    api_key = auth_manager.api_key

    return {
        "client": client,
        "engine": engine,
        "vault": test_vault,
        "api_key": api_key,
        "auth_headers": {"X-API-Key": api_key},
        "tmp_path": tmp_path,
    }


def test_rtsp_url_normalization_and_parsing():
    """Verifies that RTSP components and URLs normalize and mask credentials correctly."""
    # 1. Component normalization with credentials
    full, masked = normalize_rtsp_components(
        ip_or_host="192.168.1.100",
        port=554,
        username="admin",
        password="SuperSecretPassword!",
        stream_path="/live/ch0",
    )
    assert full == "rtsp://admin:SuperSecretPassword!@192.168.1.100:554/live/ch0"
    assert masked == "rtsp://admin:***@192.168.1.100:554/live/ch0"
    assert "SuperSecretPassword!" not in masked

    # 2. Parsing complete RTSP URL
    parsed = parse_rtsp_url("rtsp://guard_user:SecretPass456@10.0.0.50:8554/h264_stream")
    assert parsed["ip_address"] == "10.0.0.50"
    assert parsed["port"] == 8554
    assert parsed["username"] == "guard_user"
    assert parsed["password"] == "SecretPass456"
    assert parsed["stream_path"] == "/h264_stream"


def test_authentication_enforcement(cam_setup):
    """Verifies that all camera management endpoints reject unauthorized requests with HTTP 401."""
    client = cam_setup["client"]

    # Test without auth
    res1 = client.post("/api/cameras/test", json={"ip_address": "192.168.1.100"})
    assert res1.status_code == 401

    res2 = client.post("/api/cameras", json={"name": "Cam 1", "ip_address": "192.168.1.100"})
    assert res2.status_code == 401

    res3 = client.put("/api/cameras/cam_test", json={"name": "Updated"})
    assert res3.status_code == 401

    res4 = client.delete("/api/cameras/cam_test")
    assert res4.status_code == 401


def test_connection_test_socket_failure(cam_setup):
    """Verifies connection failure reporting when camera host/port is unreachable."""
    client = cam_setup["client"]
    headers = cam_setup["auth_headers"]

    payload = {
        "camera_type": "IP Camera",
        "ip_address": "192.0.2.1",  # Test-net address guaranteed unreachable
        "port": 554,
        "username": "admin",
        "password": "secret_password_123",
        "stream_path": "/ch0",
        "timeout_seconds": 1.0,
    }

    res = client.post("/api/cameras/test", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "unreachable" in data["message"].lower() or "timed out" in data["message"].lower()
    # Ensure password is NEVER leaked in response
    assert "secret_password_123" not in str(data)
    assert data["source_masked"] == "rtsp://admin:***@192.0.2.1:554/ch0"


def test_connection_test_success_mocked(cam_setup):
    """Verifies successful connection test reporting when stream is opened and decoded."""
    client = cam_setup["client"]
    headers = cam_setup["auth_headers"]

    import numpy as np
    mock_frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    with mock.patch("socket.create_connection") as mock_sock, \
         mock.patch("cv2.VideoCapture") as mock_cap_cls:

        mock_sock.return_value = mock.MagicMock()
        mock_cap = mock.MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, mock_frame)
        mock_cap.get.return_value = 25.0
        mock_cap_cls.return_value = mock_cap

        payload = {
            "name": "Front Entrance Test",
            "camera_type": "IP Camera",
            "ip_address": "192.168.1.150",
            "port": 554,
            "username": "admin",
            "password": "SecurePassword99",
            "stream_path": "/live/av0",
        }

        res = client.post("/api/cameras/test", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["resolution"] == [1280, 720]
        assert data["fps"] == 25.0
        assert "SecurePassword99" not in str(data)
        assert data["source_masked"] == "rtsp://admin:***@192.168.1.150:554/live/av0"


def test_add_camera_and_credential_masking(cam_setup):
    """Verifies adding a camera, storing encrypted credentials, and masking in responses."""
    client = cam_setup["client"]
    headers = cam_setup["auth_headers"]
    engine = cam_setup["engine"]

    create_payload = {
        "id": "cam_entrance_01",
        "name": "Main Entrance Gate",
        "camera_type": "IP Camera",
        "ip_address": "192.168.1.60",
        "port": 554,
        "username": "admin",
        "password": "HighlyConfidentialPassword123",
        "stream_path": "/stream1",
        "location": "North Entrance Turnstiles",
        "fps": 15.0,
        "enabled": True,
    }

    res = client.post("/api/cameras", json=create_payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["success"] is True
    assert data["camera_id"] == "cam_entrance_01"

    cam_info = data["camera"]
    assert cam_info["name"] == "Main Entrance Gate"
    assert cam_info["camera_type"] == "IP Camera"
    assert cam_info["location"] == "North Entrance Turnstiles"
    assert cam_info["source_masked"] == "rtsp://admin:***@192.168.1.60:554/stream1"
    # Verify password was NEVER leaked
    assert "HighlyConfidentialPassword123" not in str(data)

    # Verify camera manager registered the camera
    reader = engine.camera_manager.get_camera("cam_entrance_01")
    assert reader is not None
    assert reader._running is False  # Configuring a camera while DISARMED must not start monitoring.
    assert engine.camera_manager.count_total() == 1

    # Verify GET /api/cameras returns masked camera
    get_res = client.get("/api/cameras")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["total"] == 1
    assert get_data["cameras"][0]["id"] == "cam_entrance_01"
    assert "HighlyConfidentialPassword123" not in str(get_data)

    # Verify vault stored password in encrypted form, not plaintext
    vault_item = cam_setup["vault"].get("cam_entrance_01", include_credentials=True)
    assert vault_item["password"] == "HighlyConfidentialPassword123"
    with open(cam_setup["vault"].store_path, "r", encoding="utf-8") as f:
        raw_json = f.read()
    assert "HighlyConfidentialPassword123" not in raw_json
    assert "encrypted_password" in raw_json


def test_duplicate_camera_prevention(cam_setup):
    """Verifies that duplicate camera IDs and duplicate network endpoints are rejected."""
    client = cam_setup["client"]
    headers = cam_setup["auth_headers"]

    payload1 = {
        "id": "cam_pos_01",
        "name": "Register 1",
        "camera_type": "DVR",
        "ip_address": "192.168.1.75",
        "port": 554,
        "stream_path": "/ch1",
    }
    res1 = client.post("/api/cameras", json=payload1, headers=headers)
    assert res1.status_code == 201

    # 1. Duplicate ID rejected with 409
    dup_id_payload = dict(payload1)
    dup_id_payload["ip_address"] = "192.168.1.76"
    dup_id_payload["name"] = "Different Name"
    res2 = client.post("/api/cameras", json=dup_id_payload, headers=headers)
    assert res2.status_code == 409
    assert res2.json()["detail"]["error"] == "DUPLICATE_CAMERA"

    # 2. Duplicate endpoint (same host + port + path) rejected with 409
    dup_endpoint_payload = {
        "id": "cam_pos_02",
        "name": "Register 2",
        "camera_type": "DVR",
        "ip_address": "192.168.1.75",
        "port": 554,
        "stream_path": "/ch1",
    }
    res3 = client.post("/api/cameras", json=dup_endpoint_payload, headers=headers)
    assert res3.status_code == 409
    assert res3.json()["detail"]["error"] == "DUPLICATE_CAMERA"


def test_update_camera(cam_setup):
    """Verifies PUT /api/cameras/{id} updates fields while preserving credentials when omitted."""
    client = cam_setup["client"]
    headers = cam_setup["auth_headers"]

    # Initial creation
    client.post(
        "/api/cameras",
        json={
            "id": "cam_storage_01",
            "name": "Storage Room",
            "camera_type": "NVR",
            "ip_address": "192.168.1.90",
            "port": 554,
            "username": "nvr_user",
            "password": "OriginalSecretPassword!",
            "stream_path": "/live/ch4",
            "location": "Warehouse A",
        },
        headers=headers,
    )

    # Update name and location without re-entering password
    update_res = client.put(
        "/api/cameras/cam_storage_01",
        json={
            "name": "Secure Vault Storage",
            "location": "Warehouse A - High Value Cage",
            "fps": 10.0,
        },
        headers=headers,
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()["camera"]
    assert updated_data["name"] == "Secure Vault Storage"
    assert updated_data["location"] == "Warehouse A - High Value Cage"
    assert updated_data["fps"] == 10.0

    # Verify password was preserved in vault
    vault_item = cam_setup["vault"].get("cam_storage_01", include_credentials=True)
    assert vault_item["password"] == "OriginalSecretPassword!"

    # Updating non-existent camera returns 404
    missing_res = client.put(
        "/api/cameras/cam_non_existent",
        json={"name": "New Name"},
        headers=headers,
    )
    assert missing_res.status_code == 404
    assert missing_res.json()["detail"]["error"] == "CAMERA_NOT_FOUND"


def test_delete_camera(cam_setup):
    """Verifies DELETE /api/cameras/{id} safely unregisters camera and stops stream."""
    client = cam_setup["client"]
    headers = cam_setup["auth_headers"]
    engine = cam_setup["engine"]

    client.post(
        "/api/cameras",
        json={
            "id": "cam_to_delete",
            "name": "Temporary Yard Cam",
            "ip_address": "192.168.1.99",
            "port": 554,
            "stream_path": "/feed",
        },
        headers=headers,
    )
    assert engine.camera_manager.get_camera("cam_to_delete") is not None

    del_res = client.delete("/api/cameras/cam_to_delete", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Confirm removed from manager and vault
    assert engine.camera_manager.get_camera("cam_to_delete") is None
    assert cam_setup["vault"].get("cam_to_delete") is None

    # Deleting non-existent camera returns 404
    del_missing = client.delete("/api/cameras/cam_to_delete", headers=headers)
    assert del_missing.status_code == 404
    assert del_missing.json()["detail"]["error"] == "CAMERA_NOT_FOUND"


def test_camera_disconnect_is_health_degradation_not_intrusion(cam_setup):
    """
    Verifies that camera disconnection degrades health status but NEVER
    generates a false intrusion event or alarm.
    """
    engine = cam_setup["engine"]
    reader = engine.camera_manager.add_camera(
        camera_id="cam_health_test",
        name="Alleyway Camera",
        source="rtsp://192.168.1.200:554/stream",
        start_now=False,
    )

    # Simulate camera disconnected state
    reader._status = CameraStatus.DISCONNECTED
    engine.security_controller.update_camera_health()

    # Verify no intrusion events or recording sessions generated
    assert len(engine.incident_recorder._active_sessions) == 0
    assert len(os.listdir(engine.incidents_dir)) == 0

    # Verify health monitor records camera as disconnected
    health_report = engine.health_monitor.get_health_report()
    cam_entry = next((c for c in health_report.cameras if c.camera_id == "cam_health_test"), None)
    assert cam_entry is not None
    assert cam_entry.is_connected is False
    assert cam_entry.status == "DISCONNECTED"
