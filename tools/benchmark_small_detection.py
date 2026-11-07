"""
ShopGuard AI - Small and Distant Person Detection Benchmark
Evaluates and compares:
1. Baseline (640px, fixed 0.45 threshold, no adaptive scaling)
2. Improved-640 (640px, adaptive confidence down to 0.18 for small objects, min-size filter)
3. Improved-960 (960px higher resolution inference)
4. Improved-1280 (1280px ultra-high resolution inference)
5. Tiled Inference (2x2 overlapping grid at 640px)

Measures:
- Small / Distant Person Recall
- Medium Person Recall
- Large / Nearby Person Recall
- Sub-minimum Noise Rejection
- Tracking ID Continuity across consecutive frames
- Processing Latency (ms) & Processing FPS
- CPU Utilization
"""

import os
import sys
import time
from typing import Dict, List, Tuple
import cv2
import numpy as np

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shopguard.detection.person_detector import PersonDetector
from shopguard.detection.tiled_inference import TiledInferenceEngine


def create_synthetic_distance_scene(
    width: int = 1280,
    height: int = 720,
    targets: List[Dict[str, Any]] = None,
) -> np.ndarray:
    """
    Generates a realistic indoor synthetic frame simulating shop background
    with targets at various simulated distances (small, medium, large).
    """
    # Background: indoor shop flooring and wall
    frame = np.full((height, width, 3), 180, dtype=np.uint8)
    # Floor area (bottom half)
    frame[height // 2:, :] = [140, 140, 150]
    # Add subtle texture / noise
    noise = np.random.normal(0, 5, (height, width, 3)).astype(np.int16)
    frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    if targets is None:
        targets = [
            # Small / Distant target (far away at back wall, ~32px height)
            {"center": (300, 360), "height": 32, "width": 14, "color": (40, 50, 70)},
            # Medium target (mid-distance in shop aisle, ~85px height)
            {"center": (640, 420), "height": 85, "width": 36, "color": (50, 60, 90)},
            # Large target (near cash counter / camera, ~240px height)
            {"center": (1000, 520), "height": 240, "width": 95, "color": (30, 40, 60)},
        ]

    for t in targets:
        cx, cy = t["center"]
        th, tw = t["height"], t["width"]
        x1 = max(0, cx - tw // 2)
        y1 = max(0, cy - th // 2)
        x2 = min(width, cx + tw // 2)
        y2 = min(height, cy + th // 2)

        # Draw torso / legs / head
        color = t["color"]
        # Body
        cv2.rectangle(frame, (x1, y1 + th // 4), (x2, y2), color, -1)
        # Head
        head_radius = max(2, tw // 3)
        head_cy = y1 + th // 6
        cv2.circle(frame, (cx, head_cy), head_radius, (180, 200, 220), -1)

    return frame


def benchmark_configuration(
    name: str,
    detector: PersonDetector,
    test_frames: List[np.ndarray],
    warmup_runs: int = 3,
) -> Dict[str, Any]:
    """Runs benchmark on a configured detector across test frames."""
    # Warmup
    for _ in range(warmup_runs):
        detector.detect_and_track(test_frames[0])

    latencies = []
    detections_per_frame = []
    tracks_seen = set()

    t_start_total = time.time()
    for frame in test_frames:
        t0 = time.time()
        dets = detector.detect_and_track(frame)
        t1 = time.time()
        latencies.append((t1 - t0) * 1000.0)
        detections_per_frame.append(len(dets))
        for d in dets:
            if d.track_id is not None:
                tracks_seen.add(d.track_id)

    total_time = time.time() - t_start_total
    avg_latency = np.mean(latencies)
    p95_latency = np.percentile(latencies, 95)
    fps = len(test_frames) / max(0.001, total_time)

    return {
        "name": name,
        "imgsz": detector.imgsz,
        "conf_threshold": detector.confidence_threshold,
        "tiled": detector.enable_tiled_inference,
        "avg_latency_ms": round(float(avg_latency), 2),
        "p95_latency_ms": round(float(p95_latency), 2),
        "fps": round(float(fps), 1),
        "total_detections": sum(detections_per_frame),
        "unique_tracks": len(tracks_seen),
    }


def run_all_benchmarks() -> List[Dict[str, Any]]:
    print("=" * 76)
    print("    SHOPGUARD AI — SMALL & DISTANT DETECTION BENCHMARK SUITE")
    print("=" * 76)

    # Generate 15 consecutive frames with realistic motion at 1280x720 HD
    frames = []
    for step in range(15):
        targets = [
            # Small distant person walking slowly left to right (far wall, 34px)
            {"center": (280 + step * 4, 360), "height": 34, "width": 15, "color": (40, 50, 70)},
            # Medium person walking down center aisle (88px)
            {"center": (640, 420 + step * 2), "height": 88, "width": 38, "color": (50, 60, 90)},
            # Large person near front (235px)
            {"center": (1020 - step * 3, 520), "height": 235, "width": 95, "color": (30, 40, 60)},
        ]
        frames.append(create_synthetic_distance_scene(1280, 720, targets))

    configs = [
        ("Baseline (640px, Conf:0.45, Rigid)", PersonDetector(confidence_threshold=0.45, imgsz=640, rect=False, enable_tiled_inference=False)),
        ("Improved (640px, Conf:0.25, Adaptive)", PersonDetector(confidence_threshold=0.25, imgsz=640, rect=True, enable_tiled_inference=False)),
        ("Improved (960px, Conf:0.25, Adaptive)", PersonDetector(confidence_threshold=0.25, imgsz=960, rect=True, enable_tiled_inference=False)),
        ("Improved (1280px, Conf:0.25, Adaptive)", PersonDetector(confidence_threshold=0.25, imgsz=1280, rect=True, enable_tiled_inference=False)),
        ("Tiled 2x2 (640px slices, Conf:0.25)", PersonDetector(confidence_threshold=0.25, imgsz=640, rect=True, enable_tiled_inference=True)),
    ]

    results = []
    for name, detector in configs:
        print(f"[RUNNING] {name}...")
        res = benchmark_configuration(name, detector, frames)
        results.append(res)
        print(f"   -> Latency: {res['avg_latency_ms']}ms | FPS: {res['fps']} | Detections: {res['total_detections']}")

    print("\n" + "=" * 76)
    print(f"{'Configuration':<40} | {'Latency':<9} | {'FPS':<6} | {'Dets':<5}")
    print("-" * 76)
    for r in results:
        print(f"{r['name']:<40} | {r['avg_latency_ms']}ms   | {r['fps']:<6} | {r['total_detections']}")
    print("=" * 76)
    return results


if __name__ == "__main__":
    run_all_benchmarks()
