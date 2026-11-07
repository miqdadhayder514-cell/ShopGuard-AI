import json
import os
import time
import numpy as np
import pytest

from shopguard.recording.video_buffer import VideoBuffer
from shopguard.recording.incident_recorder import IncidentRecorder
from shopguard.intrusion.intrusion_detector import IntrusionEvent, EventType


def test_video_buffer_rolling_and_retrieval():
    """Tests that VideoBuffer maintains frames and evicts older ones."""
    buf = VideoBuffer(buffer_seconds=2.0, fps=5.0)

    # Frame shape 100x100x3
    dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)

    # Push frames at t = 10.0, 10.5, 11.0, 11.5, 12.0
    buf.append(dummy_frame, timestamp=10.0)
    buf.append(dummy_frame, timestamp=10.5)
    buf.append(dummy_frame, timestamp=11.0)
    buf.append(dummy_frame, timestamp=11.5)
    buf.append(dummy_frame, timestamp=12.0)

    # All 5 within 2s of 12.0 (cutoff 10.0)
    frames = buf.get_frames()
    assert len(frames) >= 4

    # Add frame at t = 13.0 -> frame at 10.0 and 10.5 should be evicted (cutoff 11.0)
    buf.append(dummy_frame, timestamp=13.0)
    remaining = buf.get_frames()
    timestamps = [t for _, t in remaining]
    assert min(timestamps) >= 11.0

    # Retrieve only frames since t = 12.0
    subset = buf.get_frames(start_timestamp=12.0)
    assert len(subset) == 2


def test_incident_metadata_and_video_saved(tmp_path):
    """Requirement 11: Incident metadata is saved with complete JSON specifications and video."""
    output_dir = os.path.join(tmp_path, "incidents")
    recorder = IncidentRecorder(
        output_directory=output_dir,
        pre_event_seconds=1.0,
        post_event_seconds=1.0,
        fps=5.0,
        enabled=True,
    )

    dummy_frame = np.ones((64, 64, 3), dtype=np.uint8) * 128
    now = time.time()

    pre_frames = [
        (dummy_frame, now - 0.4),
        (dummy_frame, now - 0.2),
    ]

    event = IntrusionEvent(
        event_id="test_evt_001",
        camera_id="cam_test",
        zone_id="zone_front",
        zone_name="Front Protected Zone",
        event_type=EventType.PERSON_ENTERED_RESTRICTED_ZONE,
        track_id=42,
        confidence=0.92,
        bbox=(10, 10, 40, 50),
        timestamp=now,
        persistence_seconds=2.1,
    )

    recorder.trigger_incident(event, camera_name="Front Entrance", pre_frames=pre_frames)

    # Feed post-event frames until target duration met
    recorder.on_new_frame("cam_test", dummy_frame, now + 0.5)
    recorder.on_new_frame("cam_test", dummy_frame, now + 1.2)  # Exceeds post_event_seconds (1.0s)

    # Shutdown recorder to flush writer queue
    recorder.shutdown()

    # Verify that files were created
    date_str = time.strftime("%Y-%m-%d", time.localtime(now))
    cam_folder = os.path.join(output_dir, date_str, "cam_test")
    assert os.path.exists(cam_folder), f"Expected folder {cam_folder} not found"

    files = os.listdir(cam_folder)
    json_files = [f for f in files if f.endswith(".json")]
    video_files = [f for f in files if f.endswith(".mp4") or f.endswith(".avi")]

    assert len(json_files) == 1, f"Expected 1 JSON metadata file, found: {json_files}"
    assert len(video_files) == 1, f"Expected 1 video recording, found: {video_files}"

    # Verify JSON content
    with open(os.path.join(cam_folder, json_files[0]), "r") as f:
        meta = json.load(f)

    assert meta["incident_id"] == "test_evt_001"
    assert meta["camera_id"] == "cam_test"
    assert meta["camera_name"] == "Front Entrance"
    assert meta["event_type"] == EventType.PERSON_ENTERED_RESTRICTED_ZONE.value
    assert meta["track_id"] == 42
    assert meta["detection_confidence"] == 0.92
    assert meta["zone_id"] == "zone_front"
    assert meta["review_status"] == "UNREVIEWED"
    assert meta["total_frames"] >= 3
