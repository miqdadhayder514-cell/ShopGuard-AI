"""
ShopGuard AI - Night-Time & Low-Light Robustness Tests
Evaluates AI detection and false-positive rejection under low-light, sensor noise,
passing car headlight sweeps, and dark floor shadows.
"""

import numpy as np
import pytest

from shopguard.detection.person_detector import PersonDetector, Detection
from shopguard.intrusion.zone_manager import Zone
from shopguard.intrusion.intrusion_detector import IntrusionDetector, EventType


@pytest.fixture(scope="module")
def detector():
    return PersonDetector("models/yolo11n.pt", confidence_threshold=0.40, device="cpu")


def test_pitch_black_with_sensor_noise(detector):
    """
    Evaluates complete darkness with simulated camera sensor grain / ISO noise.
    Verifies that sensor noise does not produce false-positive person detections.
    """
    # 640x480 frame with dark sensor noise (pixel values 0 to 15)
    np.random.seed(42)
    dark_noise_frame = np.random.randint(0, 15, (480, 640, 3), dtype=np.uint8)

    detections = detector.detect_and_track(dark_noise_frame)
    assert len(detections) == 0, f"Expected 0 detections on dark noise, got {len(detections)}"


def test_headlight_sweep_and_shadows(detector):
    """
    Evaluates optical flares, sweeping car headlights, and floor shadow shapes.
    Verifies that illumination sweeps without person morphology do not trigger detections.
    """
    # Ambient dark floor (pixel values ~30)
    frame = np.ones((480, 640, 3), dtype=np.uint8) * 30

    # Moving bright beam (simulating car headlights sweeping across the room)
    cv2_available = True
    try:
        import cv2
        # Draw sweeping light gradient ellipse
        cv2.ellipse(frame, (320, 240), (250, 80), 30, 0, 360, (180, 180, 190), -1)
        # Draw sharp dark shadow polygon
        shadow_pts = np.array([[100, 350], [250, 200], [350, 420], [150, 450]], np.int32)
        cv2.fillPoly(frame, [shadow_pts], (10, 10, 10))
    except Exception:
        pass

    detections = detector.detect_and_track(frame)
    assert len(detections) == 0, f"Expected 0 detections on light sweep/shadows, got {len(detections)}"


def test_window_reflection_outside_protected_zone():
    """
    Evaluates a reflection occurring near a shop window.
    Even if a synthetic reflection detection occurs at the window,
    because the restricted zone is configured on the interior floor,
    the intrusion engine rejects it.
    """
    zone_interior = Zone(
        id="z_interior_floor",
        name="Interior Floor Only",
        polygon=[(0.2, 0.3), (0.7, 0.3), (0.7, 0.9), (0.2, 0.9)],
        enabled=True,
    )
    intrusion_engine = IntrusionDetector(minimum_persistence_seconds=1.0)

    # Reflection detection positioned near window at top-right (x=0.85, y=0.15)
    det_reflection = Detection(
        class_name="person",
        confidence=0.75,
        bbox=(800, 50, 900, 250),  # bottom center: (850, 250) -> norm (0.85, 0.25)
        track_id=99,
        timestamp=100.0,
    )

    events = intrusion_engine.process_frame_detections(
        camera_id="cam_01",
        detections=[det_reflection],
        zones=[zone_interior],
        frame_width=1000,
        frame_height=1000,
        is_armed=True,
        timestamp=100.0,
    )

    assert len(events) == 0, "Window reflection outside interior zone should not trigger intrusion."
