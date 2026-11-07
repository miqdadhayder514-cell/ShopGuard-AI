from dataclasses import dataclass, asdict
import json
import os
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np

from ..utils.logger import get_logger

logger = get_logger("intrusion.zone")


@dataclass
class Zone:
    """Represents a restricted security zone defined by a normalized polygon."""
    id: str
    name: str
    polygon: List[Tuple[float, float]]  # List of (x, y) where x, y in [0.0, 1.0]
    enabled: bool = True

    def validate(self) -> Tuple[bool, Optional[str]]:
        """
        Validates polygon structure and ensures all vertices are normalized within [0.0, 1.0].
        Returns (is_valid: bool, error_message: Optional[str]).
        """
        if not self.polygon or not isinstance(self.polygon, (list, tuple)):
            return False, f"Zone '{self.id}' polygon must be a list of coordinate pairs."

        if len(self.polygon) < 3:
            return False, f"Zone '{self.id}' polygon requires at least 3 vertices, got {len(self.polygon)}."

        for idx, pt in enumerate(self.polygon):
            if not isinstance(pt, (list, tuple)) or len(pt) != 2:
                return False, f"Zone '{self.id}' vertex {idx} must be a 2-element (x, y) coordinate pair."
            try:
                x, y = float(pt[0]), float(pt[1])
            except (ValueError, TypeError):
                return False, f"Zone '{self.id}' vertex {idx} contains non-numeric coordinates: {pt}."

            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                return False, f"Zone '{self.id}' vertex {idx} ({x}, {y}) is outside normalized range [0.0, 1.0]."

        return True, None

    def to_pixel_polygon(self, frame_width: int, frame_height: int) -> np.ndarray:
        """Converts normalized polygon coordinates to integer pixel coordinates."""
        w, h = float(frame_width), float(frame_height)
        pixel_pts = [
            [int(round(pt[0] * w)), int(round(pt[1] * h))]
            for pt in self.polygon
        ]
        return np.array(pixel_pts, dtype=np.int32).reshape((-1, 1, 2))

    def contains_normalized_point(self, point_norm: Tuple[float, float]) -> bool:
        """
        Tests whether a normalized point (x, y) is inside or on the boundary of the zone.
        Uses OpenCV cv2.pointPolygonTest.
        """
        is_valid, _ = self.validate()
        if not is_valid:
            return False

        poly_np = np.array(self.polygon, dtype=np.float32).reshape((-1, 1, 2))
        res = cv2.pointPolygonTest(poly_np, (float(point_norm[0]), float(point_norm[1])), measureDist=False)
        return res >= 0

    def contains_pixel_point(self, point_pixel: Tuple[float, float], frame_width: int, frame_height: int) -> bool:
        """Tests whether a pixel point (x, y) is inside the zone."""
        w, h = max(1, frame_width), max(1, frame_height)
        norm_x = point_pixel[0] / w
        norm_y = point_pixel[1] / h
        return self.contains_normalized_point((norm_x, norm_y))


class ZoneManager:
    """
    Manages restricted zones across all cameras.
    Loads, validates, and saves configuration to JSON.
    """

    def __init__(self, config_file: Optional[str] = "config/zones.example.json", strict: bool = False):
        self.config_file = config_file
        self.strict = strict
        self._zones: Dict[str, List[Zone]] = {}  # camera_id -> List[Zone]

        if config_file and os.path.exists(config_file):
            self.load_zones(config_file, strict=strict)
        elif config_file:
            logger.info(f"Zone configuration file '{config_file}' does not exist yet. Starting with empty zones.")

    def load_zones(self, config_path: str, strict: bool = False) -> bool:
        """Loads and validates zones from a JSON file."""
        if not os.path.exists(config_path):
            logger.error(f"Cannot load zones: file not found at '{config_path}'")
            return False

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                raise ValueError("Zone configuration JSON root must be an object mapping camera_id to zone lists.")

            loaded_zones: Dict[str, List[Zone]] = {}
            for cam_id, zone_list in data.items():
                if not isinstance(zone_list, list):
                    raise ValueError(f"Zone entry for camera '{cam_id}' must be a list of zone definitions.")

                loaded_zones[cam_id] = []
                for z_data in zone_list:
                    raw_poly = z_data.get("polygon", [])
                    poly = [(float(pt[0]), float(pt[1])) for pt in raw_poly]
                    zone = Zone(
                        id=z_data.get("id", f"zone_{len(loaded_zones[cam_id]) + 1}"),
                        name=z_data.get("name", "Restricted Zone"),
                        polygon=poly,
                        enabled=z_data.get("enabled", True),
                    )

                    is_valid, err = zone.validate()
                    if not is_valid:
                        msg = f"Invalid zone configuration for camera '{cam_id}': {err}"
                        logger.error(msg)
                        if strict:
                            raise ValueError(msg)
                        continue

                    loaded_zones[cam_id].append(zone)

            self._zones = loaded_zones
            self.config_file = config_path
            logger.info(f"Loaded zones for {len(self._zones)} camera(s) from '{config_path}'.")
            return True

        except Exception as e:
            logger.error(f"Failed to parse zone configuration file '{config_path}': {e}")
            if strict:
                raise
            return False

    def save_zones(self, config_path: Optional[str] = None) -> bool:
        """Saves current zones to a JSON file."""
        target_path = config_path or self.config_file
        if not target_path:
            logger.error("No target path specified for saving zones.")
            return False

        try:
            os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
            export_data = {}
            for cam_id, zone_list in self._zones.items():
                export_data[cam_id] = [asdict(z) for z in zone_list]

            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)

            logger.info(f"Saved {sum(len(z) for z in self._zones.values())} zone(s) to '{target_path}'.")
            return True

        except Exception as e:
            logger.error(f"Failed to save zones to '{target_path}': {e}")
            return False

    def get_all_zones(self) -> Dict[str, List[Zone]]:
        """Returns the dictionary mapping camera IDs to their lists of zones."""
        return self._zones.copy()

    def get_zones(self, camera_id: str, enabled_only: bool = True) -> List[Zone]:
        """Retrieves list of validated zones for a specific camera."""
        zones = self._zones.get(camera_id, [])
        valid_zones = [z for z in zones if z.validate()[0]]
        if enabled_only:
            return [z for z in valid_zones if z.enabled]
        return valid_zones

    def has_enabled_zones(self, camera_id: str) -> bool:
        """Returns True if the camera has at least one valid, enabled restricted zone."""
        zones = self.get_zones(camera_id, enabled_only=True)
        return len(zones) > 0

    def set_zones(self, camera_id: str, zones: List[Zone]) -> None:
        """Sets the zones for a given camera."""
        self._zones[camera_id] = zones

    def add_zone(self, camera_id: str, zone: Zone) -> None:
        """Appends a zone to the given camera."""
        if camera_id not in self._zones:
            self._zones[camera_id] = []
        self._zones[camera_id].append(zone)
