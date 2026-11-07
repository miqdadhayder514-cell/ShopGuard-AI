"""
ShopGuard AI - Interactive Zone Configuration Tool
Allows security installers to select polygon points on a camera frame and save them to zones JSON.
Usage:
    python tools/zone_editor.py --camera camera_01 --config config/config.yaml
"""

import argparse
import json
import os
import sys
import cv2
import numpy as np

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shopguard.utils.helpers import load_config
from shopguard.utils.logger import setup_logger, mask_url

logger = setup_logger("data/logs")


class ZoneEditor:
    def __init__(self, camera_id: str, stream_source: str, zones_file: str):
        self.camera_id = camera_id
        self.stream_source = stream_source
        self.zones_file = zones_file
        self.current_points = []
        self.frame = None
        self.display_frame = None
        self.window_name = f"ShopGuard AI - Zone Editor ({camera_id})"

    def _mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            # Add point
            self.current_points.append((x, y))
            logger.info(f"Point added: ({x}, {y})")
            self._redraw()
        elif event == cv2.EVENT_RBUTTONDOWN:
            # Undo last point
            if self.current_points:
                removed = self.current_points.pop()
                logger.info(f"Removed point: {removed}")
                self._redraw()

    def _redraw(self):
        if self.frame is None:
            return
        self.display_frame = self.frame.copy()

        # Draw existing points
        for i, pt in enumerate(self.current_points):
            cv2.circle(self.display_frame, pt, 5, (0, 0, 255), -1)
            cv2.putText(
                self.display_frame,
                str(i + 1),
                (pt[0] + 7, pt[1] - 7),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 255),
                1,
            )

        # Draw lines between points
        if len(self.current_points) >= 2:
            pts_array = np.array(self.current_points, np.int32).reshape((-1, 1, 2))
            cv2.polylines(self.display_frame, [pts_array], isClosed=False, color=(0, 255, 0), thickness=2)

        # Instructions HUD
        h, w = self.display_frame.shape[:2]
        hud = "Left Click: Add Point | Right Click: Undo | S: Save Zone | C: Clear | Q: Quit"
        cv2.rectangle(self.display_frame, (0, h - 35), (w, h), (30, 30, 30), -1)
        cv2.putText(
            self.display_frame,
            hud,
            (10, h - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        cv2.imshow(self.window_name, self.display_frame)

    def run(self):
        print(f"\nOpening stream for '{self.camera_id}' ({mask_url(self.stream_source)})...")
        cap = cv2.VideoCapture(self.stream_source)
        if not cap.isOpened():
            print(f"Error: Unable to open camera source '{mask_url(self.stream_source)}'")
            return

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            print("Error: Could not capture a valid frame from the camera stream.")
            return

        self.frame = frame
        h, w = frame.shape[:2]

        cv2.namedWindow(self.window_name)
        cv2.setMouseCallback(self.window_name, self._mouse_callback)
        self._redraw()

        print("\n=== Zone Editor Controls ===")
        print("  - Left click on the video frame to place polygon points.")
        print("  - Right click to undo the last point.")
        print("  - Press 's' to save the polygon.")
        print("  - Press 'c' to clear current points.")
        print("  - Press 'q' to quit.")

        while True:
            key = cv2.waitKey(20) & 0xFF
            if key == ord("q"):
                print("Exiting zone editor without saving.")
                break
            elif key == ord("c"):
                self.current_points.clear()
                self._redraw()
                print("Cleared points.")
            elif key == ord("s"):
                if len(self.current_points) < 3:
                    print("Error: A restricted zone polygon requires at least 3 points.")
                    continue

                # Close polygon
                pts_array = np.array(self.current_points, np.int32).reshape((-1, 1, 2))
                cv2.polylines(self.display_frame, [pts_array], isClosed=True, color=(0, 255, 0), thickness=2)
                cv2.imshow(self.window_name, self.display_frame)
                cv2.waitKey(100)

                zone_id = input("\nEnter Zone ID (e.g. zone_entrance): ").strip() or "zone_1"
                zone_name = input("Enter Zone Name (e.g. Front Door Protected Area): ").strip() or "Restricted Zone"

                # Normalize coordinates
                normalized_poly = [
                    [round(pt[0] / float(w), 4), round(pt[1] / float(h), 4)]
                    for pt in self.current_points
                ]

                self._save_to_file(zone_id, zone_name, normalized_poly)
                break

        cv2.destroyAllWindows()

    def _save_to_file(self, zone_id: str, zone_name: str, polygon: list):
        zones_data = {}
        if os.path.exists(self.zones_file):
            try:
                with open(self.zones_file, "r", encoding="utf-8") as f:
                    zones_data = json.load(f)
            except Exception:
                zones_data = {}

        if self.camera_id not in zones_data:
            zones_data[self.camera_id] = []

        # Replace existing or append
        existing = [z for z in zones_data[self.camera_id] if z.get("id") == zone_id]
        if existing:
            existing[0]["name"] = zone_name
            existing[0]["polygon"] = polygon
            existing[0]["enabled"] = True
        else:
            zones_data[self.camera_id].append({
                "id": zone_id,
                "name": zone_name,
                "polygon": polygon,
                "enabled": True,
            })

        os.makedirs(os.path.dirname(os.path.abspath(self.zones_file)), exist_ok=True)
        with open(self.zones_file, "w", encoding="utf-8") as f:
            json.dump(zones_data, f, indent=2)

        print(f"\n[SUCCESS] Zone '{zone_name}' ({zone_id}) saved to {self.zones_file}")


def main():
    parser = argparse.ArgumentParser(description="ShopGuard AI Zone Configuration Editor")
    parser.add_argument("--config", default="config/config.yaml", help="Path to config.yaml")
    parser.add_argument("--camera", default="camera_01", help="Camera ID to configure zones for")
    args = parser.parse_args()

    cfg = load_config(args.config)
    zones_file = cfg.get("zones", {}).get("configuration_file", "config/zones.example.json")

    # Find camera
    cams = cfg.get("cameras", [])
    selected_cam = next((c for c in cams if c.get("id") == args.camera), None)

    if not selected_cam:
        print(f"Error: Camera '{args.camera}' not found in {args.config}")
        sys.exit(1)

    source = selected_cam.get("source", "")
    editor = ZoneEditor(args.camera, source, zones_file)
    editor.run()


if __name__ == "__main__":
    main()
