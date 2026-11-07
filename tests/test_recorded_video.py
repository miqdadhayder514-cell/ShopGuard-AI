import json
import os
import time
import cv2
import pytest

from shopguard.testing.recorded_video_tester import RecordedVideoTester, select_video_file
from shopguard.security.security_controller import SecurityState
from shopguard.intrusion.zone_manager import Zone
from shopguard.detection.person_detector import Detection
from tools.generate_test_video import generate_synthetic_video


class MockPersonDetector:
    """Mock detector generating deterministic person detections for unit testing."""
    def __init__(self, bbox=(100, 80, 160, 200), track_id=1, is_loaded=True):
        self.bbox = bbox
        self.track_id = track_id
        self.is_loaded = is_loaded
        self.load_error = None

    def detect_and_track(self, frame, timestamp=None):
        if self.bbox is None:
            return []
        return [
            Detection(
                class_name="person",
                confidence=0.92,
                bbox=self.bbox,
                track_id=self.track_id,
                timestamp=timestamp,
            )
        ]


@pytest.fixture
def test_video_file(tmp_path):
    """Generates a 3-second test video at 10 FPS."""
    path = os.path.join(tmp_path, "recorded_sample.mp4")
    assert generate_synthetic_video(
        path,
        duration_seconds=3,
        fps=10,
        width=320,
        height=240,
        include_person=True,
    )
    return str(path)


def test_recorded_video_load_and_metadata(test_video_file, tmp_path):
    """Verifies that RecordedVideoTester accurately extracts video dimensions, FPS, and frame count."""
    tester = RecordedVideoTester(
        video_path=test_video_file,
        output_incident_dir=str(tmp_path / "incidents"),
        show_gui=False,
    )
    assert tester.width == 320
    assert tester.height == 240
    assert tester.total_frames == 30
    assert tester.fps == 10.0
    assert tester.duration_seconds == 3.0
    tester.stop()


def test_recorded_video_disarmed_suppression(test_video_file, tmp_path):
    """Verifies that in DISARMED mode, even when a person is in the zone, zero incidents are triggered."""
    incident_dir = tmp_path / "incidents"
    # Mock detector puts person inside zone
    mock_detector = MockPersonDetector(bbox=(100, 80, 160, 200), track_id=1)
    tester = RecordedVideoTester(
        video_path=test_video_file,
        initial_state=SecurityState.DISARMED,
        output_incident_dir=str(incident_dir),
        show_gui=False,
        auto_arm=False,
        person_detector=mock_detector,
    )
    assert tester.security_controller.state == SecurityState.DISARMED

    # Add zone covering the mock person: (130/320, 200/240) = (0.406, 0.833)
    tester.zone_manager.add_zone(
        tester.camera_id,
        Zone(
            id="zone_test",
            name="Protected Counter",
            polygon=[(0.2, 0.5), (0.8, 0.5), (0.8, 0.95), (0.2, 0.95)],
            enabled=True,
        ),
    )

    results = tester.run()

    assert results["total_frames_analyzed"] > 0
    assert results["incidents_count"] == 0
    assert len(results["incidents"]) == 0


def test_recorded_video_armed_intrusion_detection(test_video_file, tmp_path):
    """Verifies that in ARMED mode, a person in the protected zone is detected and triggers an incident."""
    incident_dir = tmp_path / "incidents"
    mock_detector = MockPersonDetector(bbox=(100, 80, 160, 200), track_id=2)
    tester = RecordedVideoTester(
        video_path=test_video_file,
        output_incident_dir=str(incident_dir),
        show_gui=False,
        auto_arm=True,
        person_detector=mock_detector,
    )
    assert tester.security_controller.state == SecurityState.ARMED

    tester.zone_manager.set_zones(
        tester.camera_id,
        [
            Zone(
                id="zone_test_armed",
                name="Restricted Cash Area",
                polygon=[(0.2, 0.5), (0.8, 0.5), (0.8, 0.95), (0.2, 0.95)],
                enabled=True,
            )
        ],
    )

    results = tester.run()

    assert results["total_frames_analyzed"] > 0
    assert results["incidents_count"] >= 1
    evt = results["incidents"][0]
    assert evt.zone_name == "Restricted Cash Area"
    assert evt.track_id == 2
    assert evt.confidence == 0.92


def test_recorded_video_dynamic_arm_disarm_controls(test_video_file, tmp_path):
    """Verifies that arm() and disarm() can be invoked dynamically and transition state."""
    tester = RecordedVideoTester(
        video_path=test_video_file,
        initial_state=SecurityState.DISARMED,
        output_incident_dir=str(tmp_path / "incidents"),
        show_gui=False,
    )
    assert tester.security_controller.state == SecurityState.DISARMED

    # Test arming
    success, msg, _ = tester.arm()
    assert success is True
    assert tester.security_controller.state == SecurityState.ARMED

    # Test disarming
    d_success, d_msg = tester.disarm()
    assert d_success is True
    assert tester.security_controller.state == SecurityState.DISARMED
    tester.stop()


def test_recorded_video_playback_controls(test_video_file, tmp_path):
    """Verifies pause, resume, speed control, restart, and single-frame step."""
    tester = RecordedVideoTester(
        video_path=test_video_file,
        output_incident_dir=str(tmp_path / "incidents"),
        show_gui=False,
    )

    # Pause & Resume
    assert tester.is_paused is False
    tester.pause()
    assert tester.is_paused is True
    tester.resume()
    assert tester.is_paused is False

    # Speed controls
    tester.set_speed(2.0)
    assert tester.playback_speed == 2.0
    tester.set_speed(0.5)
    assert tester.playback_speed == 0.5

    # Single-frame step
    tester.step_forward()
    assert tester.step_one_frame is True

    # Restart
    tester.current_frame_idx = 15
    tester.restart()
    assert tester.current_frame_idx == 0

    tester.stop()


def test_recorded_video_incident_recording_and_metadata(test_video_file, tmp_path):
    """
    Verifies that simulated incidents save playable MP4 files and JSON metadata
    with explicit recorded_video tagging and rtsp_verified == False.
    """
    incident_dir = tmp_path / "incidents"
    mock_detector = MockPersonDetector(bbox=(100, 80, 160, 200), track_id=3)
    tester = RecordedVideoTester(
        video_path=test_video_file,
        output_incident_dir=str(incident_dir),
        show_gui=False,
        auto_arm=True,
        person_detector=mock_detector,
    )

    tester.zone_manager.set_zones(
        tester.camera_id,
        [
            Zone(
                id="zone_counter",
                name="Cash Counter",
                polygon=[(0.2, 0.5), (0.8, 0.5), (0.8, 0.95), (0.2, 0.95)],
                enabled=True,
            )
        ],
    )

    results = tester.run()
    assert results["incidents_count"] >= 1

    # Wait briefly for background incident writer queue to flush
    time.sleep(0.5)

    # Find saved JSON metadata
    json_files = []
    for root, _, files in os.walk(str(incident_dir)):
        for f in files:
            if f.endswith(".json"):
                json_files.append(os.path.join(root, f))

    assert len(json_files) >= 1, "Expected at least one incident JSON file to be saved"

    with open(json_files[0], "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["source_type"] == "recorded_video"
    assert meta["simulation_mode"] is True
    assert meta["rtsp_verified"] is False
    assert meta["zone_name"] == "Cash Counter"
    assert "video_filename" in meta

    # Check video file exists and can be opened
    video_path = os.path.join(os.path.dirname(json_files[0]), meta["video_filename"])
    assert os.path.isfile(video_path)
    cap = cv2.VideoCapture(video_path)
    assert cap.isOpened()
    ret, frame = cap.read()
    assert ret is True
    assert frame is not None
    cap.release()


def test_select_video_file_fallback(tmp_path):
    """Verifies that select_video_file correctly handles explicitly provided paths."""
    test_file = str(tmp_path / "custom.mp4")
    with open(test_file, "w") as f:
        f.write("dummy")

    resolved = select_video_file(path_arg=test_file, prompt_terminal=False)
    assert os.path.abspath(resolved) == os.path.abspath(test_file)
