import json
import os
import pytest
import numpy as np

from shopguard.intrusion.zone_manager import Zone, ZoneManager
from shopguard.detection.person_detector import Detection


def test_zone_point_containment():
    """Tests polygon containment logic using normalized coordinates."""
    zone = Zone(
        id="zone_test",
        name="Test Zone",
        polygon=[(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)],
        enabled=True,
    )

    # Point clearly inside
    assert zone.contains_normalized_point((0.5, 0.5)) is True
    # Point clearly outside
    assert zone.contains_normalized_point((0.1, 0.5)) is False
    assert zone.contains_normalized_point((0.9, 0.5)) is False
    assert zone.contains_normalized_point((0.5, 0.1)) is False
    assert zone.contains_normalized_point((0.5, 0.9)) is False

    # Pixel coordinate test on 1920x1080 frame
    assert zone.contains_pixel_point((960, 540), 1920, 1080) is True
    assert zone.contains_pixel_point((100, 100), 1920, 1080) is False


def test_bottom_center_calculation():
    """Verifies bottom-center anchor point formula: ((x1 + x2)/2, y2)."""
    det = Detection(
        class_name="person",
        confidence=0.85,
        bbox=(100, 200, 300, 600),
        track_id=1,
        timestamp=1000.0,
    )

    cx, cy = det.bottom_center
    assert cx == 200.0
    assert cy == 600.0

    # On a 1000x1000 frame
    norm_x, norm_y = det.bottom_center_normalized(1000, 1000)
    assert norm_x == 0.20
    assert norm_y == 0.60


def test_invalid_polygon_rejection():
    """Tests that invalid polygons (<3 vertices, out-of-range coordinates) are rejected."""
    # Fewer than 3 points
    z_two_pts = Zone(id="z1", name="Two Points", polygon=[(0.1, 0.1), (0.2, 0.2)])
    valid, err = z_two_pts.validate()
    assert valid is False
    assert "at least 3 vertices" in err

    # Out of [0.0, 1.0] range
    z_out_of_bounds = Zone(id="z2", name="Out Bounds", polygon=[(0.1, 0.1), (1.5, 0.5), (0.2, 0.9)])
    valid, err = z_out_of_bounds.validate()
    assert valid is False
    assert "outside normalized range" in err

    # Negative coordinates
    z_neg = Zone(id="z3", name="Negative", polygon=[(-0.1, 0.1), (0.5, 0.5), (0.2, 0.9)])
    valid, err = z_neg.validate()
    assert valid is False


def test_zone_manager_load_and_save(tmp_path):
    """Tests loading and exporting zones to JSON."""
    test_file = os.path.join(tmp_path, "zones_test.json")

    sample_data = {
        "cam_front": [
            {
                "id": "zone_entrance",
                "name": "Entrance Area",
                "polygon": [[0.1, 0.1], [0.4, 0.1], [0.4, 0.5], [0.1, 0.5]],
                "enabled": True,
            }
        ]
    }
    with open(test_file, "w") as f:
        json.dump(sample_data, f)

    zm = ZoneManager(test_file)
    assert zm.has_enabled_zones("cam_front") is True
    assert zm.has_enabled_zones("cam_back") is False

    zones = zm.get_zones("cam_front")
    assert len(zones) == 1
    assert zones[0].id == "zone_entrance"

    # Add a zone and save back
    new_zone = Zone(
        id="zone_cash",
        name="Cash Register",
        polygon=[[0.6, 0.6], [0.9, 0.6], [0.9, 0.9], [0.6, 0.9]],
        enabled=True,
    )
    zm.add_zone("cam_front", new_zone)
    save_file = os.path.join(tmp_path, "saved_zones.json")
    assert zm.save_zones(save_file) is True

    # Re-read and check
    zm_reloaded = ZoneManager(save_file)
    assert len(zm_reloaded.get_zones("cam_front")) == 2
