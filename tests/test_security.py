import pytest
from unittest.mock import MagicMock

from shopguard.security.security_controller import SecurityController, SecurityState
from shopguard.utils.helpers import validate_config


def test_system_starts_in_disarmed_state():
    """Requirement 1: System starts in DISARMED state."""
    controller = SecurityController()
    assert controller.state == SecurityState.DISARMED
    assert controller.is_armed is False


def test_valid_camera_and_zone_configuration_allows_arming():
    """Requirement 3: Valid camera and zone configuration allows arming."""
    controller = SecurityController()

    mock_cam_mgr = MagicMock()
    mock_cam_mgr.count_total.return_value = 1
    mock_cam_mgr.count_connected.return_value = 1
    mock_cam_mgr.all_connected.return_value = True
    mock_cam_mgr.get_all_cameras.return_value = {"cam_01": MagicMock()}

    mock_detector = MagicMock()
    mock_detector.is_loaded = True
    mock_detector.load_error = None

    mock_zone_mgr = MagicMock()
    mock_zone_mgr.has_enabled_zones.return_value = True

    controller.bind_dependencies(
        camera_manager=mock_cam_mgr,
        person_detector=mock_detector,
        zone_manager=mock_zone_mgr,
        is_processing_active=lambda: True,
    )

    success, msg, check_result = controller.arm()
    assert success is True
    assert controller.state == SecurityState.ARMED
    assert controller.is_armed is True


def test_missing_camera_prevents_full_arming():
    """Requirement 4: Missing camera prevents full arming."""
    controller = SecurityController()

    mock_cam_mgr = MagicMock()
    mock_cam_mgr.count_total.return_value = 1
    mock_cam_mgr.count_connected.return_value = 0  # 0 connected
    mock_cam_mgr.all_connected.return_value = False
    mock_cam_mgr.get_all_cameras.return_value = {"cam_01": MagicMock()}

    mock_detector = MagicMock()
    mock_detector.is_loaded = True

    mock_zone_mgr = MagicMock()
    mock_zone_mgr.has_enabled_zones.return_value = True

    controller.bind_dependencies(
        camera_manager=mock_cam_mgr,
        person_detector=mock_detector,
        zone_manager=mock_zone_mgr,
        is_processing_active=lambda: True,
    )

    success, msg, check_result = controller.arm()
    assert success is False
    assert controller.state == SecurityState.DISARMED
    assert "None of the enabled cameras are currently connected" in msg


def test_missing_zones_prevents_arming():
    """Requirement 5: Missing zones prevents arming."""
    controller = SecurityController()

    mock_cam_mgr = MagicMock()
    mock_cam_mgr.count_total.return_value = 1
    mock_cam_mgr.count_connected.return_value = 1
    mock_cam_mgr.all_connected.return_value = True
    mock_cam_mgr.get_all_cameras.return_value = {"cam_01": MagicMock()}

    mock_detector = MagicMock()
    mock_detector.is_loaded = True

    mock_zone_mgr = MagicMock()
    mock_zone_mgr.has_enabled_zones.return_value = False  # No zones configured

    controller.bind_dependencies(
        camera_manager=mock_cam_mgr,
        person_detector=mock_detector,
        zone_manager=mock_zone_mgr,
        is_processing_active=lambda: True,
    )

    success, msg, check_result = controller.arm()
    assert success is False
    assert controller.state == SecurityState.DISARMED
    assert "No valid protected zones are configured" in msg


def test_disarming_transitions_to_disarmed():
    """Requirement 12: Disarming returns state to DISARMED."""
    controller = SecurityController(initial_state=SecurityState.ARMED)
    assert controller.is_armed is True

    success, msg = controller.disarm()
    assert success is True
    assert controller.state == SecurityState.DISARMED
    assert controller.is_armed is False


def test_invalid_configuration_reporting():
    """Requirement 13: Invalid configuration is reported clearly."""
    # Test missing section
    with pytest.raises(ValueError, match="Missing required configuration section"):
        validate_config({"security": {}})

    # Test invalid confidence threshold
    invalid_conf = {
        "security": {"confidence_threshold": 1.5},
        "recording": {},
        "ai": {},
        "cameras": [{"id": "cam_1", "source": "test.mp4"}],
    }
    with pytest.raises(ValueError, match="Invalid confidence_threshold"):
        validate_config(invalid_conf)

    # Test duplicate camera id
    dup_cam = {
        "security": {"confidence_threshold": 0.5},
        "recording": {},
        "ai": {},
        "cameras": [
            {"id": "cam_1", "source": "test1.mp4"},
            {"id": "cam_1", "source": "test2.mp4"},
        ],
    }
    with pytest.raises(ValueError, match="Duplicate camera id detected"):
        validate_config(dup_cam)


def test_partial_and_offline_health_updates():
    """Tests health degradation to PARTIAL and OFFLINE when cameras disconnect."""
    controller = SecurityController(initial_state=SecurityState.ARMED)

    mock_cam_mgr = MagicMock()
    mock_cam_mgr.count_total.return_value = 2
    mock_cam_mgr.count_connected.return_value = 1  # 1 of 2 connected

    controller.bind_dependencies(
        camera_manager=mock_cam_mgr,
        person_detector=MagicMock(is_loaded=True),
        zone_manager=MagicMock(has_enabled_zones=lambda c: True),
        is_processing_active=lambda: True,
    )

    controller.update_camera_health()
    assert controller.state == SecurityState.PARTIAL

    # When all drop
    mock_cam_mgr.count_connected.return_value = 0
    controller.update_camera_health()
    assert controller.state == SecurityState.OFFLINE
