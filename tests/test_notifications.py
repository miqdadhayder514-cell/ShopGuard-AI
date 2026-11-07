"""
ShopGuard AI - Automated Test Suite for Firebase Cloud Messaging (FCM) Integration
Verifies:
1. FcmNotificationManager token registration, unregistration, and persistence.
2. Token input validation and masking.
3. Graceful handling when Firebase credentials are not present.
4. REST API endpoints (/api/notifications/register-token, unregister-token, status, test).
5. Authentication enforcement on notification endpoints (HTTP 401 on unauthorized).
6. Auto-pruning of dead tokens upon FCM delivery failure.
"""

from datetime import datetime, timezone
import json
import os
import unittest.mock as mock
import pytest
from fastapi.testclient import TestClient

from shopguard.notifications.fcm_notifier import FcmNotificationManager, mask_token
from shopguard.agent.server import create_app
from shopguard.agent.security_auth import auth_manager
from shopguard.security.security_controller import SecurityController, SecurityState


class DummyEngine:
    def __init__(self):
        self.security_controller = SecurityController(initial_state=SecurityState.DISARMED)
        self.health_monitor = mock.MagicMock()
        self.camera_manager = mock.MagicMock()
        self.camera_manager.get_all_cameras.return_value = {}


def test_mask_token():
    assert mask_token("") == "fcm_empty"
    assert mask_token("abc") == "fcm_***"
    assert mask_token("abcdefghijklmno") == "abcdef...jklmno"


def test_token_registration_and_persistence(tmp_path):
    tokens_file = str(tmp_path / "fcm_tokens.json")
    manager = FcmNotificationManager(
        credentials_file=str(tmp_path / "nonexistent_creds.json"),
        tokens_file=tokens_file,
        app_name="test_app_1",
    )

    assert manager.get_token_count() == 0

    # Register first token
    t1 = "device_token_sample_1234567890_alpha"
    count = manager.register_token(t1, device_name="Pixel 8 Pro", app_version="1.0.0")
    assert count == 1
    assert manager.get_token_count() == 1
    assert manager.get_tokens() == [t1]

    # Verify persisted to disk
    assert os.path.isfile(tokens_file)
    with open(tokens_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert t1 in data["tokens"]
    assert data["tokens"][t1]["device_name"] == "Pixel 8 Pro"

    # Register second token
    t2 = "device_token_sample_9876543210_beta"
    count = manager.register_token(t2, device_name="Galaxy S24", app_version="1.0.0")
    assert count == 2
    assert manager.get_token_count() == 2

    # Unregister first token
    removed = manager.unregister_token(t1)
    assert removed is True
    assert manager.get_token_count() == 1
    assert manager.get_tokens() == [t2]

    # Unregister already removed token
    assert manager.unregister_token(t1) is False


def test_token_validation(tmp_path):
    tokens_file = str(tmp_path / "fcm_tokens.json")
    manager = FcmNotificationManager(
        credentials_file=str(tmp_path / "nonexistent.json"),
        tokens_file=tokens_file,
        app_name="test_app_val",
    )

    # Empty token
    with pytest.raises(ValueError, match="non-empty"):
        manager.register_token("")

    # Too short
    with pytest.raises(ValueError, match="Invalid FCM token length"):
        manager.register_token("short")


def test_security_alert_unconfigured(tmp_path):
    tokens_file = str(tmp_path / "fcm_tokens.json")
    manager = FcmNotificationManager(
        credentials_file=str(tmp_path / "nonexistent.json"),
        tokens_file=tokens_file,
        app_name="test_app_unconf",
    )
    manager.register_token("sample_token_1234567890123")

    result = manager.send_security_alert(
        incident_id="inc_001",
        event_type="INTRUSION",
        camera_name="Warehouse Front",
    )
    assert result["status"] == "unconfigured"
    assert result["sent"] == 0


def test_auto_pruning_on_unregistered_error(tmp_path):
    from firebase_admin import messaging

    tokens_file = str(tmp_path / "fcm_tokens.json")
    manager = FcmNotificationManager(
        credentials_file=str(tmp_path / "nonexistent.json"),
        tokens_file=tokens_file,
        app_name="test_app_pruning",
    )
    manager.is_configured = True
    manager._app = mock.MagicMock()

    t_valid = "token_valid_1234567890_alpha"
    t_dead = "token_dead_9876543210_beta"
    manager.register_token(t_valid)
    manager.register_token(t_dead)
    assert manager.get_token_count() == 2

    # Mock send_each response (new API: individual Message objects via send_each)
    mock_resp_valid = mock.MagicMock(success=True)
    mock_resp_dead = mock.MagicMock(
        success=False,
        exception=messaging.UnregisteredError("Requested entity was not found."),
    )
    mock_batch = mock.MagicMock(
        success_count=1,
        failure_count=1,
        responses=[mock_resp_valid, mock_resp_dead],
    )

    with mock.patch("firebase_admin.messaging.send_each", return_value=mock_batch):
        res = manager.send_security_alert(
            incident_id="inc_prune_test",
            event_type="PERSON_DETECTED",
            camera_name="Main Entry",
            camera_id="cam_01",
        )

    assert res["sent"] == 1
    assert res["failed"] == 1
    assert res["pruned"] == 1
    # t_dead should be automatically pruned from manager and file
    assert manager.get_token_count() == 1
    assert manager.get_tokens() == [t_valid]


# =============================================================================
# REST API ENDPOINT TESTS
# =============================================================================

@pytest.fixture
def api_client(tmp_path):
    tokens_file = str(tmp_path / "fcm_tokens.json")
    manager = FcmNotificationManager(
        credentials_file=str(tmp_path / "nonexistent.json"),
        tokens_file=tokens_file,
        app_name="test_app_api",
    )
    dummy_engine = DummyEngine()
    app = create_app(
        engine=dummy_engine,
        state_file=str(tmp_path / "state.json"),
        fcm_notifier=manager,
    )
    return TestClient(app)


def test_register_token_endpoint_auth_required(api_client):
    # Missing API key -> 401
    resp = api_client.post(
        "/api/notifications/register-token",
        json={"token": "test_token_1234567890_alpha"},
    )
    assert resp.status_code == 401


def test_register_and_unregister_token_endpoint_flow(api_client):
    valid_key = auth_manager.api_key
    headers = {"X-API-Key": valid_key}

    # 1. Check initial status
    resp = api_client.get("/api/notifications/status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tokens_count"] == 0

    # 2. Register token with invalid payload (too short) -> 422 or 400
    bad_resp = api_client.post(
        "/api/notifications/register-token",
        json={"token": "short"},
        headers=headers,
    )
    assert bad_resp.status_code == 422

    # 3. Register valid token -> 200
    token_str = "fcm_registration_token_1234567890_sample"
    reg_resp = api_client.post(
        "/api/notifications/register-token",
        json={
            "token": token_str,
            "device_name": "Samsung Galaxy S23",
            "app_version": "1.0.0",
        },
        headers=headers,
    )
    assert reg_resp.status_code == 200
    reg_data = reg_resp.json()
    assert reg_data["success"] is True
    assert reg_data["tokens_count"] == 1

    # 4. Verify token count in status
    resp = api_client.get("/api/notifications/status", headers=headers)
    assert resp.json()["tokens_count"] == 1

    # 5. Send test notification
    test_resp = api_client.post(
        "/api/notifications/test",
        json={"title": "Test Ping", "body": "Ping Body"},
        headers=headers,
    )
    assert test_resp.status_code == 200

    # 6. Unregister token -> 200
    unreg_resp = api_client.post(
        "/api/notifications/unregister-token",
        json={"token": token_str},
        headers=headers,
    )
    assert unreg_resp.status_code == 200
    assert unreg_resp.json()["tokens_count"] == 0

    # 7. Verify count is now 0
    resp = api_client.get("/api/notifications/status", headers=headers)
    assert resp.json()["tokens_count"] == 0
