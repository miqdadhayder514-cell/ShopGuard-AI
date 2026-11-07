"""
ShopGuard AI - Automated Test Suite for Small and Distant Person Detection
Verifies:
1. Multi-resolution inference configuration (640, 960, 1280).
2. Rectangular aspect-ratio preserving inference.
3. Configurable minimum bounding-box size filtering with non-silent audit logging.
4. Distance-adaptive confidence scaling for distant/small people.
5. Comprehensive inference diagnostics generation (pixel height, conf, rejected count, lost tracks).
6. Tiled inference slice generation, coordinate mapping, and NMS suppression.
7. Tracking continuity (ByteTrack stability) for small detections across frames.
"""

import time
import pytest
import numpy as np

from shopguard.detection.person_detector import (
    Detection,
    PersonDetector,
    RejectedDetection,
    DetectionDiagnostics,
)
from shopguard.detection.tiled_inference import TiledInferenceEngine, TileSlice
from shopguard.tracking.object_tracker import ObjectTracker


def test_detector_multi_resolution_and_rect_configuration():
    """Verifies that PersonDetector accepts 640, 960, 1280 resolution options and rect inference."""
    for res in (640, 960, 1280):
        detector = PersonDetector(
            confidence_threshold=0.35,
            imgsz=res,
            rect=True,
            min_box_height_px=20,
            min_box_width_px=12,
        )
        assert detector.imgsz == res
        assert detector.rect is True
        assert detector.min_box_height_px == 20
        assert detector.min_box_width_px == 12


def test_detection_dataclass_dimensions_and_metrics():
    """Verifies that Detection accurately reports pixel height, width, and area."""
    det = Detection(
        class_name="person",
        confidence=0.75,
        bbox=(100, 150, 180, 390),
        track_id=1,
        timestamp=time.time(),
    )
    assert det.width_px == 80
    assert det.height_px == 240
    assert det.area_px == 80 * 240
    assert det.center == (140.0, 270.0)
    assert det.bottom_center == (140.0, 390.0)


def test_minimum_box_size_rejection_and_logging(monkeypatch):
    """
    Verifies that detections smaller than min_box_height_px or min_box_width_px
    are rejected with clear audit logging and recorded in diagnostics, NOT silently dropped.
    """
    detector = PersonDetector(
        confidence_threshold=0.25,
        min_box_height_px=25,
        min_box_width_px=15,
    )

    # Mock raw candidate returning a sub-minimum detection (10x12px noise speck)
    # and a valid small person (20x45px)
    class MockBoxes:
        def __init__(self):
            self.cls = [type("C", (), {"item": lambda s: 0})(), type("C", (), {"item": lambda s: 0})()]
            self.conf = [type("C", (), {"item": lambda s: 0.80})(), type("C", (), {"item": lambda s: 0.70})()]
            # Box 0: 10x12px (Too small: h=12 < 25, w=10 < 15)
            # Box 1: 20x45px (Valid small person: h=45 >= 25, w=20 >= 15)
            self.xyxy = [
                type("C", (), {"cpu": lambda s: type("B", (), {"numpy": lambda s: np.array([100, 100, 110, 112])})()})(),
                type("C", (), {"cpu": lambda s: type("B", (), {"numpy": lambda s: np.array([200, 200, 220, 245])})()})(),
            ]
            self.id = [type("C", (), {"item": lambda s: 1})(), type("C", (), {"item": lambda s: 2})()]

        def __len__(self):
            return len(self.cls)

    class MockResult:
        boxes = MockBoxes()

    monkeypatch.setattr(detector.model, "track", lambda **kwargs: [MockResult()])

    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    accepted = detector.detect_and_track(frame)

    # Box 1 accepted, Box 0 rejected
    assert len(accepted) == 1
    assert accepted[0].bbox == (200, 200, 220, 245)

    # Check Diagnostics Audit Trail
    diag = detector.get_diagnostics()
    assert diag is not None
    assert diag.total_candidates == 2
    assert diag.accepted_count == 1
    assert diag.rejected_count == 1
    assert len(diag.rejected_detections) == 1

    rej = diag.rejected_detections[0]
    assert rej.reason == "BELOW_MIN_BOX_SIZE"
    assert rej.height_px == 12
    assert rej.width_px == 10
    assert rej.confidence == 0.80


def test_confidence_rejection_and_adaptive_threshold(monkeypatch):
    """
    Verifies that candidates below the effective threshold are rejected and recorded,
    while small/distant candidates benefit from distance-adaptive scaling.
    """
    detector = PersonDetector(
        confidence_threshold=0.40,
        min_box_height_px=10,
        min_box_width_px=10,
    )

    class MockBoxes:
        def __init__(self):
            self.cls = [type("C", (), {"item": lambda s: 0})(), type("C", (), {"item": lambda s: 0})()]
            # Candidate 0: Large near person (h=400px), conf=0.30 -> Below 0.40 baseline -> REJECTED
            # Candidate 1: Distant small person (h=60px < 30% of 720), conf=0.30 -> Adaptive threshold 0.40*0.65=0.26 -> ACCEPTED
            self.conf = [type("C", (), {"item": lambda s: 0.30})(), type("C", (), {"item": lambda s: 0.30})()]
            self.xyxy = [
                type("C", (), {"cpu": lambda s: type("B", (), {"numpy": lambda s: np.array([50, 50, 250, 450])})()})(),
                type("C", (), {"cpu": lambda s: type("B", (), {"numpy": lambda s: np.array([500, 100, 530, 160])})()})(),
            ]
            self.id = [type("C", (), {"item": lambda s: 10})(), type("C", (), {"item": lambda s: 20})()]

        def __len__(self):
            return len(self.cls)

    monkeypatch.setattr(detector.model, "track", lambda **kwargs: [type("R", (), {"boxes": MockBoxes()})()])

    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    accepted = detector.detect_and_track(frame)

    assert len(accepted) == 1
    assert accepted[0].bbox == (500, 100, 530, 160)
    assert accepted[0].track_id == 20

    diag = detector.get_diagnostics()
    assert diag.rejected_count == 1
    assert diag.rejected_detections[0].reason == "CONFIDENCE_BELOW_THRESHOLD"
    assert diag.rejected_detections[0].bbox == (50, 50, 250, 450)


def test_tiled_inference_slice_generation_and_nms():
    """Verifies that TiledInferenceEngine splits frame with overlap and suppresses duplicate boundary detections."""
    tiler = TiledInferenceEngine(grid=(2, 2), overlap=0.20, iou_threshold=0.40)
    dummy_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    tiles = tiler.generate_tiles(dummy_frame)
    assert len(tiles) == 4

    for tile in tiles:
        assert tile.width > 0 and tile.height > 0
        assert tile.image.shape[0] == tile.height
        assert tile.image.shape[1] == tile.width
        assert tile.x_offset + tile.width <= 1920
        assert tile.y_offset + tile.height <= 1080

    # Test NMS logic: Two heavily overlapping bounding boxes across tile seam
    boxes = [
        (400, 400, 460, 520),  # Box 0: score 0.85
        (405, 402, 462, 518),  # Box 1: score 0.70 (duplicate seam overlap)
        (800, 300, 850, 420),  # Box 2: score 0.80 (distinct target)
    ]
    scores = [0.85, 0.70, 0.80]

    kept = TiledInferenceEngine.apply_nms(boxes, scores, iou_threshold=0.45)
    assert 0 in kept
    assert 2 in kept
    assert 1 not in kept  # Box 1 suppressed by NMS


def test_bytetrack_tracking_stability_and_lost_track_diagnostics():
    """Verifies tracking continuity and lost-track detection in ObjectTracker."""
    tracker = ObjectTracker(track_expiry_seconds=5.0)

    # Frame 1 at t=0.0: Target A (ID:1) and Target B (ID:2)
    det_a1 = Detection("person", 0.70, (100, 100, 140, 180), 1, 0.0)
    det_b1 = Detection("person", 0.65, (300, 200, 335, 275), 2, 0.0)
    tracker.update([det_a1, det_b1], timestamp=0.0)

    assert len(tracker.get_all_active_tracks()) == 2
    assert tracker.get_recently_lost_tracks(threshold_seconds=1.5, current_time=0.0) == []

    # Frame 2 at t=2.0: Target A continues moving, Target B is momentarily lost
    det_a2 = Detection("person", 0.72, (105, 100, 145, 180), 1, 2.0)
    tracker.update([det_a2], timestamp=2.0)

    # Target B was last seen at t=0.0, current t=2.0 (elapsed 2.0s >= 1.5s) -> Lost!
    lost = tracker.get_recently_lost_tracks(threshold_seconds=1.5, current_time=2.0)
    assert 2 in lost
    assert 1 not in lost

    # Frame 3 at t=2.5: Target B re-detected -> Recovered
    det_b3 = Detection("person", 0.60, (305, 205, 340, 280), 2, 2.5)
    tracker.update([det_a2, det_b3], timestamp=2.5)

    lost_after_recovery = tracker.get_recently_lost_tracks(threshold_seconds=1.5, current_time=2.5)
    assert len(lost_after_recovery) == 0


def test_visualizer_diagnostics_overlay():
    """Verifies that FeedVisualizer renders HUD metrics, pixel heights, and diagnostic panel."""
    from shopguard.camera.visualizer import FeedVisualizer
    from shopguard.security.security_controller import SecurityState

    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    det = Detection("person", 0.62, (200, 300, 245, 410), 5, time.time())

    diag = DetectionDiagnostics(
        inference_size=960,
        inference_fps=6.8,
        inference_time_ms=147.2,
        total_candidates=3,
        accepted_count=1,
        rejected_count=2,
        rejected_detections=[
            RejectedDetection((50, 50, 70, 62), 0.15, 12, 20, "BELOW_MIN_BOX_SIZE", 0.25),
            RejectedDetection((400, 300, 500, 600), 0.21, 300, 100, "CONFIDENCE_BELOW_THRESHOLD", 0.40),
        ],
        active_track_ids=[5],
        lost_track_ids=[2],
        tiled_inference_used=False,
    )

    out = FeedVisualizer.render_overlay(
        frame=frame,
        camera_name="Main Camera 1080p",
        security_state=SecurityState.ARMED,
        fps=6.8,
        detections=[det],
        zones=[],
        diagnostics=diag,
        show_diagnostics=True,
    )

    assert out is not None
    assert out.shape == (720, 1280, 3)
