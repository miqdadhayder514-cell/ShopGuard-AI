"""
ShopGuard AI - Synthetic Video Generator
Generates local MP4 test videos featuring simulated shop scenes:
- Empty shop (no person)
- Person outside protected zone
- Person entering and lingering in protected zone
"""

import os
from typing import Tuple
import cv2
import numpy as np


def generate_synthetic_video(
    output_path: str = "data/temporary/test_feed.mp4",
    duration_seconds: int = 10,
    fps: int = 5,
    width: int = 640,
    height: int = 480,
    include_person: bool = True,
    person_path_x: Tuple[int, int] = (50, 220),  # Start x and end x
    person_y: int = 220,
):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    if not writer.isOpened():
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    if not writer.isOpened():
        print(f"Error: Could not open VideoWriter for {output_path}")
        return False

    total_frames = int(duration_seconds * fps)
    person_w, person_h = 40, 100
    start_x, end_x = person_path_x

    for f_idx in range(total_frames):
        # Create background (shop floor pattern)
        frame = np.ones((height, width, 3), dtype=np.uint8) * 220

        # Draw floor tiles
        for x in range(0, width, 60):
            cv2.line(frame, (x, 0), (x, height), (200, 200, 200), 1)
        for y in range(0, height, 60):
            cv2.line(frame, (0, y), (width, y), (200, 200, 200), 1)

        # Draw a simulated shelf on the right
        cv2.rectangle(frame, (450, 150), (600, 450), (140, 110, 80), -1)
        cv2.putText(frame, "SHELF", (480, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Timestamp on frame
        sec = f_idx / max(1, fps)
        cv2.putText(
            frame,
            f"SYNTHETIC CCTV TEST STREAM - {sec:.1f}s",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (40, 40, 40),
            1,
        )

        if include_person:
            # Move person across first 2 seconds, then remain stationary
            move_frames = max(1, int(2.0 * fps))
            progress = min(1.0, f_idx / float(move_frames))
            px = int(start_x + progress * (end_x - start_x))
            py = int(person_y)

            # Draw person silhouette
            # Head
            cv2.circle(frame, (px + person_w // 2, py - 15), 12, (50, 50, 150), -1)
            # Body / Torso
            cv2.rectangle(frame, (px + 5, py), (px + person_w - 5, py + 55), (60, 60, 60), -1)
            # Legs
            cv2.rectangle(frame, (px + 7, py + 55), (px + 17, py + person_h), (30, 30, 30), -1)
            cv2.rectangle(frame, (px + 23, py + 55), (px + 33, py + person_h), (30, 30, 30), -1)

        writer.write(frame)

    writer.release()
    return True


if __name__ == "__main__":
    generate_synthetic_video()
