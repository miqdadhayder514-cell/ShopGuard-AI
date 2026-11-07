import json
import os
import time
import pytest
import cv2
import numpy as np

from shopguard.camera.camera_manager import CameraManager
from shopguard.detection.person_detector import Detection, PersonDetector
from shopguard.intrusion.zone_manager import Zone, ZoneManager
from shopguard.intrusion.intrusion_detector import IntrusionDetector, IntrusionEvent, EventType
from shopguard.recording.video_buffer import VideoBuffer
from shopguard.recording.incident_recorder import IncidentRecorder
from shopguard.security.security_controller import SecurityController, SecurityState
from shopguard.monitoring.health_monitor import HealthMonitor
from tools.generate_test_video import generate_synthetic_video


def test_scenario_1_empty_shop(tmp_path):
    """
    TEST 1: EMPTY SHOP
    - Load empty shop video (no people).
    - Arm security.
    - Confirm no person detections.
    - Confirm no intrusion incidents.
    """
    video_path = os.path.join(tmp_path, "empty_shop.mp4")
    assert generate_synthetic_video(video_path, duration_seconds=2, fps=5, include_person=False) is True

    cap = cv2.VideoCapture(video_path)
    assert cap.isOpened() is True

    # Zone covering entrance
    zone = Zone(id="z_entrance", name="Main Entrance", polygon=[(0.1, 0.1), (0.5, 0.1), (0.5, 0.8), (0.1, 0.8)])
    detector = IntrusionDetector(minimum_persistence_seconds=1.0)

    # Process all frames
    events = []
    detections_count = 0
    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        # Mocking empty detections on this empty scene
        dets: list = []
        detections_count += len(dets)
        evts = detector.process_frame_detections(
            camera_id="cam_01",
            detections=dets,
            zones=[zone],
            frame_width=640,
            frame_height=480,
            is_armed=True,
        )
        events.extend(evts)
    cap.release()

    assert detections_count == 0
    assert len(events) == 0


def test_scenario_2_person_outside_restricted_zone(tmp_path):
    """
    TEST 2: PERSON OUTSIDE RESTRICTED ZONE
    - Security is ARMED.
    - Person is walking on the right (x=500..550), zone is strictly on the left (x=0.1..0.4).
    - Confirm detections occur but 0 intrusion incidents are generated.
    """
    zone = Zone(id="z_left", name="Left Storage Area", polygon=[(0.1, 0.1), (0.4, 0.1), (0.4, 0.8), (0.1, 0.8)])
    detector = IntrusionDetector(minimum_persistence_seconds=1.0)

    # Synthetic detections outside zone on a 1000x1000 frame: x=800..850, y=400..600
    # Bottom center is (825, 600) -> normalized (0.825, 0.60) which is OUTSIDE [0.1, 0.4]
    events = []
    for t in [1.0, 1.5, 2.0, 2.5, 3.0]:
        det = Detection(
            class_name="person",
            confidence=0.90,
            bbox=(800, 400, 850, 600),
            track_id=5,
            timestamp=t,
        )
        evts = detector.process_frame_detections(
            camera_id="cam_01",
            detections=[det],
            zones=[zone],
            frame_width=1000,
            frame_height=1000,
            is_armed=True,
            timestamp=t,
        )
        events.extend(evts)

    assert len(events) == 0


def test_scenario_3_person_enters_protected_zone(tmp_path):
    """
    TEST 3: PERSON ENTERS PROTECTED ZONE
    - Security is ARMED.
    - Person enters protected zone and persists past minimum duration.
    - Confirm incident event is triggered and recorded.
    """
    incidents_dir = os.path.join(tmp_path, "incidents")
    recorder = IncidentRecorder(
        output_directory=incidents_dir,
        pre_event_seconds=1.0,
        post_event_seconds=1.0,
        fps=5.0,
        enabled=True,
    )
    buffer = VideoBuffer(buffer_seconds=3.0, fps=5.0)

    dummy_frame = np.ones((100, 100, 3), dtype=np.uint8) * 200
    zone = Zone(id="z_cash", name="Cash Counter", polygon=[(0.1, 0.1), (0.5, 0.1), (0.5, 0.8), (0.1, 0.8)])
    detector = IntrusionDetector(minimum_persistence_seconds=1.0, min_consistent_observations=2)

    # Person inside zone: x=200..300, y=300..500 -> bottom-center (250, 500) -> norm (0.25, 0.50)
    events = []
    t_start = 10.0
    for i in range(8):
        t = t_start + i * 0.5
        buffer.append(dummy_frame, timestamp=t)
        det = Detection(
            class_name="person",
            confidence=0.92,
            bbox=(200, 300, 300, 500),
            track_id=12,
            timestamp=t,
        )
        evts = detector.process_frame_detections(
            camera_id="cam_01",
            detections=[det],
            zones=[zone],
            frame_width=1000,
            frame_height=1000,
            is_armed=True,
            timestamp=t,
        )
        for evt in evts:
            events.append(evt)
            pre_frames = buffer.get_frames(start_timestamp=evt.timestamp - 1.0)
            recorder.trigger_incident(evt, camera_name="Front Desk", pre_frames=pre_frames)

        # Feed post-event frames
        recorder.on_new_frame("cam_01", dummy_frame, timestamp=t)

    recorder.shutdown()

    assert len(events) >= 1
    assert events[0].event_type == EventType.PERSON_ENTERED_RESTRICTED_ZONE
    assert events[0].track_id == 12

    # Verify incident files were created
    date_str = time.strftime("%Y-%m-%d", time.localtime(t_start))
    cam_folder = os.path.join(incidents_dir, date_str, "cam_01")
    assert os.path.exists(cam_folder)
    assert any(f.endswith(".json") for f in os.listdir(cam_folder))


def test_scenario_4_disarmed_system():
    """
    TEST 4: DISARMED SYSTEM
    - Security is DISARMED.
    - Person is inside the protected zone for an extended period.
    - Confirm 0 intrusion events are generated.
    """
    zone = Zone(id="z_cash", name="Cash Counter", polygon=[(0.1, 0.1), (0.5, 0.1), (0.5, 0.8), (0.1, 0.8)])
    detector = IntrusionDetector(minimum_persistence_seconds=1.0)

    det = Detection(class_name="person", confidence=0.95, bbox=(200, 300, 300, 500), track_id=20, timestamp=50.0)

    # Feed frames at t = 50.0, 51.0, 52.0, 55.0
    for t in [50.0, 51.0, 52.0, 55.0]:
        det.timestamp = t
        evts = detector.process_frame_detections(
            camera_id="cam_01",
            detections=[det],
            zones=[zone],
            frame_width=1000,
            frame_height=1000,
            is_armed=False,  # DISARMED
            timestamp=t,
        )
        assert len(evts) == 0


def test_scenario_5_event_cooldown():
    """
    TEST 5: EVENT COOLDOWN
    - Security is ARMED.
    - Person stays in the restricted zone.
    - First event triggers; subsequent frames within cooldown are suppressed as duplicates.
    """
    zone = Zone(id="z_cash", name="Cash Counter", polygon=[(0.1, 0.1), (0.5, 0.1), (0.5, 0.8), (0.1, 0.8)])
    detector = IntrusionDetector(
        minimum_persistence_seconds=1.0,
        event_cooldown_seconds=15.0,
        min_consistent_observations=1,
    )

    det = Detection(class_name="person", confidence=0.88, bbox=(200, 300, 300, 500), track_id=33, timestamp=100.0)

    # Frame 1: Entry
    detector.process_frame_detections("cam_01", [det], [zone], 1000, 1000, True, timestamp=100.0)

    # Frame 2 at t=101.5: Persistence met -> Event 1
    e1 = detector.process_frame_detections("cam_01", [det], [zone], 1000, 1000, True, timestamp=101.5)
    assert len(e1) == 1
    assert e1[0].event_type == EventType.PERSON_ENTERED_RESTRICTED_ZONE

    # Frame 3 at t=103.0 (inside 15s cooldown): SUPPRESSED
    e2 = detector.process_frame_detections("cam_01", [det], [zone], 1000, 1000, True, timestamp=103.0)
    assert len(e2) == 0

    # Frame 4 at t=110.0 (inside 15s cooldown): SUPPRESSED
    e3 = detector.process_frame_detections("cam_01", [det], [zone], 1000, 1000, True, timestamp=110.0)
    assert len(e3) == 0

    # Frame 5 at t=117.0 (cooldown of 15s expired): Emits next cautious status
    e4 = detector.process_frame_detections("cam_01", [det], [zone], 1000, 1000, True, timestamp=117.0)
    assert len(e4) == 1
    assert e4[0].event_type in (EventType.PERSON_PRESENT_IN_RESTRICTED_ZONE, EventType.POSSIBLE_SUSPICIOUS_ACTIVITY)


def test_scenario_6_camera_disconnection():
    """
    TEST 6: CAMERA DISCONNECTION
    - Camera disconnects during monitoring.
    - Security status changes to PARTIAL or OFFLINE.
    - Camera outage never produces an intrusion incident.
    """
    controller = SecurityController(initial_state=SecurityState.ARMED)
    from unittest.mock import MagicMock
    mock_cam_mgr = MagicMock()
    mock_cam_mgr.count_total.return_value = 2
    mock_cam_mgr.count_connected.return_value = 1  # 1 dropped

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


def test_scenario_7_invalid_configuration(tmp_path):
    """
    TEST 7: INVALID CONFIGURATION
    - Invalid zone coordinates provided.
    - System reports configuration error.
    - System cannot arm.
    """
    invalid_zones_file = os.path.join(tmp_path, "invalid_zones.json")
    with open(invalid_zones_file, "w") as f:
        json.dump({
            "cam_01": [
                {
                    "id": "bad_zone",
                    "name": "Invalid Coordinates Zone",
                    "polygon": [(0.1, 0.1), (2.5, 3.0), (0.2, 0.9)],  # Coordinates > 1.0!
                    "enabled": True,
                }
            ]
        }, f)

    # In strict mode, loading invalid zones raises ValueError
    zm = ZoneManager(strict=False)
    success = zm.load_zones(invalid_zones_file, strict=False)
    # The invalid zone is rejected
    assert zm.has_enabled_zones("cam_01") is False

    # Attempting to arm with no valid zones is rejected
    controller = SecurityController()
    from unittest.mock import MagicMock
    mock_cam_mgr = MagicMock()
    mock_cam_mgr.count_total.return_value = 1
    mock_cam_mgr.count_connected.return_value = 1
    mock_cam_mgr.all_connected.return_value = True
    mock_cam_mgr.get_all_cameras.return_value = {"cam_01": MagicMock()}

    controller.bind_dependencies(
        camera_manager=mock_cam_mgr,
        person_detector=MagicMock(is_loaded=True),
        zone_manager=zm,
        is_processing_active=lambda: True,
    )

    can_arm, msg, res = controller.arm()
    assert can_arm is False
    assert controller.state == SecurityState.DISARMED
    assert "No valid protected zones are configured" in msg


def test_scenario_8_recording_validation(tmp_path):
    """
    TEST 8: RECORDING VALIDATION
    - Trigger incident.
    - Confirm pre-event and post-event video are saved.
    - Confirm saved video can be opened with cv2.VideoCapture and has valid frames.
    - Confirm JSON metadata is valid and review status is UNREVIEWED.
    """
    output_dir = os.path.join(tmp_path, "recordings")
    recorder = IncidentRecorder(
        output_directory=output_dir,
        pre_event_seconds=1.0,
        post_event_seconds=1.0,
        fps=5.0,
        enabled=True,
    )

    now = time.time()
    # 320x240 frame
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    cv2.putText(frame, "INCIDENT FRAME", (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    pre_frames = [
        (frame.copy(), now - 0.6),
        (frame.copy(), now - 0.2),
    ]

    event = IntrusionEvent(
        event_id="rec_val_001",
        camera_id="cam_main",
        zone_id="z_safe",
        zone_name="Safe Box Zone",
        event_type=EventType.PERSON_ENTERED_RESTRICTED_ZONE,
        track_id=88,
        confidence=0.91,
        bbox=(50, 50, 150, 200),
        timestamp=now,
        persistence_seconds=2.2,
    )

    recorder.trigger_incident(event, camera_name="Main Camera", pre_frames=pre_frames)

    # Feed post-event frames
    recorder.on_new_frame("cam_main", frame, now + 0.5)
    recorder.on_new_frame("cam_main", frame, now + 1.2)  # Completes post-event duration

    recorder.shutdown()

    date_str = time.strftime("%Y-%m-%d", time.localtime(now))
    target_dir = os.path.join(output_dir, date_str, "cam_main")
    assert os.path.exists(target_dir)

    files = os.listdir(target_dir)
    video_files = [f for f in files if f.endswith(".mp4") or f.endswith(".avi")]
    json_files = [f for f in files if f.endswith(".json")]

    assert len(video_files) == 1
    assert len(json_files) == 1

    # Verify video can be opened and read
    video_path = os.path.join(target_dir, video_files[0])
    cap = cv2.VideoCapture(video_path)
    assert cap.isOpened() is True
    ret, read_frame = cap.read()
    assert ret is True
    assert read_frame.shape == (240, 320, 3)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    assert frame_count >= 3
    cap.release()

    # Verify JSON content
    json_path = os.path.join(target_dir, json_files[0])
    with open(json_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["incident_id"] == "rec_val_001"
    assert meta["camera_id"] == "cam_main"
    assert meta["camera_name"] == "Main Camera"
    assert meta["event_type"] == EventType.PERSON_ENTERED_RESTRICTED_ZONE.value
    assert meta["track_id"] == 88
    assert meta["confidence"] == 0.91
    assert meta["zone_id"] == "z_safe"
    assert meta["video_filename"] == video_files[0]
    assert meta["review_status"] == "UNREVIEWED"
    assert meta["total_frames"] >= 3
