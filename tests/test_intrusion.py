import pytest
from shopguard.intrusion.intrusion_detector import IntrusionDetector, EventType
from shopguard.intrusion.zone_manager import Zone
from shopguard.detection.person_detector import Detection
from shopguard.monitoring.health_monitor import HealthMonitor
from unittest.mock import MagicMock


@pytest.fixture
def test_zone():
    # Zone covers normalized square (0.2, 0.2) to (0.8, 0.8)
    return Zone(
        id="zone_main",
        name="Main Shop Floor",
        polygon=[(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)],
        enabled=True,
    )


def test_disarmed_state_does_not_generate_intrusion(test_zone):
    """Requirement 2: Disarmed state does not generate intrusion incidents."""
    detector = IntrusionDetector(
        minimum_persistence_seconds=1.0,
        event_cooldown_seconds=10.0,
        min_consistent_observations=1,
    )

    # Person located at normalized (0.5, 0.5) inside zone on a 1000x1000 frame
    det = Detection(
        class_name="person",
        confidence=0.90,
        bbox=(400, 200, 600, 500),  # bottom center: (500, 500) -> (0.5, 0.5)
        track_id=101,
        timestamp=100.0,
    )

    # In DISARMED state (is_armed=False)
    events = detector.process_frame_detections(
        camera_id="cam_01",
        detections=[det],
        zones=[test_zone],
        frame_width=1000,
        frame_height=1000,
        is_armed=False,
        timestamp=100.0,
    )
    assert len(events) == 0

    # Repeat at later timestamp
    events2 = detector.process_frame_detections(
        camera_id="cam_01",
        detections=[det],
        zones=[test_zone],
        frame_width=1000,
        frame_height=1000,
        is_armed=False,
        timestamp=105.0,
    )
    assert len(events2) == 0


def test_person_outside_restricted_zone_does_not_trigger(test_zone):
    """Requirement 6: Person outside restricted zone does not trigger intrusion."""
    detector = IntrusionDetector(
        minimum_persistence_seconds=1.0,
        event_cooldown_seconds=10.0,
        min_consistent_observations=1,
    )

    # Person located at normalized (0.1, 0.1) outside zone
    det = Detection(
        class_name="person",
        confidence=0.95,
        bbox=(50, 50, 150, 100),  # bottom center: (100, 100) -> (0.1, 0.1)
        track_id=102,
        timestamp=100.0,
    )

    # ARMED state
    events = detector.process_frame_detections(
        camera_id="cam_01",
        detections=[det],
        zones=[test_zone],
        frame_width=1000,
        frame_height=1000,
        is_armed=True,
        timestamp=100.0,
    )
    assert len(events) == 0

    # Stay outside for 10 seconds
    events2 = detector.process_frame_detections(
        camera_id="cam_01",
        detections=[det],
        zones=[test_zone],
        frame_width=1000,
        frame_height=1000,
        is_armed=True,
        timestamp=110.0,
    )
    assert len(events2) == 0


def test_person_entering_zone_triggers_after_persistence(test_zone):
    """Requirement 7: Person entering a restricted zone while armed triggers an event after configured persistence."""
    detector = IntrusionDetector(
        minimum_persistence_seconds=2.0,
        event_cooldown_seconds=30.0,
        min_consistent_observations=2,
    )

    # Person inside zone: bottom center at (500, 500)
    det = Detection(
        class_name="person",
        confidence=0.88,
        bbox=(400, 200, 600, 500),
        track_id=103,
        timestamp=100.0,
    )

    # Frame 1 at t=100.0: first observation -> duration=0.0s < 2.0s persistence -> No event
    e1 = detector.process_frame_detections(
        camera_id="cam_01",
        detections=[det],
        zones=[test_zone],
        frame_width=1000,
        frame_height=1000,
        is_armed=True,
        timestamp=100.0,
    )
    assert len(e1) == 0

    # Frame 2 at t=101.0: duration=1.0s < 2.0s -> No event
    e2 = detector.process_frame_detections(
        camera_id="cam_01",
        detections=[det],
        zones=[test_zone],
        frame_width=1000,
        frame_height=1000,
        is_armed=True,
        timestamp=101.0,
    )
    assert len(e2) == 0

    # Frame 3 at t=102.5: duration=2.5s >= 2.0s -> EVENT TRIGGERED!
    e3 = detector.process_frame_detections(
        camera_id="cam_01",
        detections=[det],
        zones=[test_zone],
        frame_width=1000,
        frame_height=1000,
        is_armed=True,
        timestamp=102.5,
    )
    assert len(e3) == 1
    evt = e3[0]
    assert evt.event_type == EventType.PERSON_ENTERED_RESTRICTED_ZONE
    assert evt.track_id == 103
    assert evt.zone_id == test_zone.id
    assert evt.confidence == 0.88


def test_duplicate_events_suppressed_and_cooldown_works(test_zone):
    """Requirements 8 & 9: Duplicate events suppressed; cooldown works."""
    detector = IntrusionDetector(
        minimum_persistence_seconds=1.0,
        event_cooldown_seconds=10.0,
        min_consistent_observations=1,
    )

    det = Detection(
        class_name="person",
        confidence=0.85,
        bbox=(400, 200, 600, 500),
        track_id=104,
        timestamp=50.0,
    )

    # First event triggered at t=51.5 (duration 1.5s)
    detector.process_frame_detections("cam_01", [det], [test_zone], 1000, 1000, True, timestamp=50.0)
    e1 = detector.process_frame_detections("cam_01", [det], [test_zone], 1000, 1000, True, timestamp=51.5)
    assert len(e1) == 1
    assert e1[0].event_type == EventType.PERSON_ENTERED_RESTRICTED_ZONE

    # Duplicate check at t=52.0 (cooldown is 10s): MUST BE SUPPRESSED
    e2 = detector.process_frame_detections("cam_01", [det], [test_zone], 1000, 1000, True, timestamp=52.0)
    assert len(e2) == 0

    # Duplicate check at t=58.0 (still inside 10s cooldown): MUST BE SUPPRESSED
    e3 = detector.process_frame_detections("cam_01", [det], [test_zone], 1000, 1000, True, timestamp=58.0)
    assert len(e3) == 0

    # At t=62.0 (cooldown elapsed): Triggers second cautious event
    e4 = detector.process_frame_detections("cam_01", [det], [test_zone], 1000, 1000, True, timestamp=62.0)
    assert len(e4) == 1
    assert e4[0].event_type in (EventType.PERSON_PRESENT_IN_RESTRICTED_ZONE, EventType.POSSIBLE_SUSPICIOUS_ACTIVITY)


def test_camera_disconnection_changes_health_without_theft_incident():
    """Requirement 10: Camera disconnection changes health status but does not create a theft incident."""
    mock_reader = MagicMock()
    mock_reader.name = "Front Entrance"
    mock_reader.is_connected = False
    mock_reader.status.value = "DISCONNECTED"
    mock_reader.last_frame_time = 0.0
    mock_reader.source = "rtsp://mock-cam/feed"

    mock_cam_mgr = MagicMock()
    mock_cam_mgr.get_all_cameras.return_value = {"cam_01": mock_reader}

    monitor = HealthMonitor(
        camera_manager=mock_cam_mgr,
        person_detector=MagicMock(is_loaded=True, model_path="yolo11n.pt", device="cpu"),
        security_controller=MagicMock(state=MagicMock(value="OFFLINE")),
    )

    report = monitor.get_health_report()
    assert report.cameras[0].is_connected is False
    assert report.cameras[0].status == "DISCONNECTED"
    assert report.overall_health in ("DEGRADED", "CRITICAL")
    # Crucially, stream disconnection does not produce any IntrusionEvent
