"""
ShopGuard AI - Camera Management & Independence Tests
Verifies that multiple cameras operate independently and that an offline/failing camera
does not block or degrade healthy camera streams.
"""

import os
import threading
import time
import pytest
import numpy as np

from shopguard.camera.camera_manager import CameraManager
from shopguard.camera.stream_reader import CameraStatus, StreamReader
from shopguard.security.security_controller import SecurityController, SecurityState
from tools.generate_test_video import generate_synthetic_video


def test_multi_camera_independence(tmp_path):
    """
    Verifies that Camera 2 operates normally and reads frames continuously
    even when Camera 1 is completely unreachable / broken.
    """
    healthy_video = os.path.join(tmp_path, "healthy_cam.mp4")
    assert generate_synthetic_video(healthy_video, duration_seconds=3, fps=5) is True

    cam_mgr = CameraManager()

    # Broken camera (invalid path / unreachable)
    reader_broken = cam_mgr.add_camera_from_config({
        "id": "cam_broken",
        "name": "Broken Camera",
        "source": "rtsp://192.0.2.1:554/unreachable_stream",  # TEST-NET-1 unreachable IP
        "enabled": True,
        "fps": 5.0,
        "connection_timeout_seconds": 1.0,
        "reconnect_interval_seconds": 2.0,
    })

    # Healthy camera (local test feed)
    reader_healthy = cam_mgr.add_camera_from_config({
        "id": "cam_healthy",
        "name": "Healthy Camera",
        "source": healthy_video,
        "enabled": True,
        "fps": 5.0,
    })

    assert reader_broken is not None
    assert reader_healthy is not None

    cam_mgr.start_all()

    # Allow healthy reader to read frames
    time.sleep(1.0)

    # Broken camera should not be connected
    assert reader_broken.is_connected is False
    assert reader_broken.status in (CameraStatus.CONNECTING, CameraStatus.RECONNECTING, CameraStatus.ERROR)

    # Healthy camera must be connected and successfully delivering frames
    assert reader_healthy.is_connected is True
    assert reader_healthy.is_ready is True
    ret, frame, ts = reader_healthy.read()
    assert ret is True
    assert frame is not None
    assert frame.shape == (480, 640, 3)

    # Verify controller state evaluates to PARTIAL coverage
    controller = SecurityController(initial_state=SecurityState.ARMED)
    controller.bind_dependencies(
        camera_manager=cam_mgr,
        person_detector=None,
        zone_manager=None,
        is_processing_active=lambda: True,
    )

    controller.update_camera_health()
    assert controller.state == SecurityState.PARTIAL
    assert controller.is_armed is True  # PARTIAL still monitors the operational camera!

    cam_mgr.stop_all()


def test_disabled_camera_is_ignored():
    """Verifies that disabled cameras in config are not registered or started."""
    cam_mgr = CameraManager()
    reader = cam_mgr.add_camera_from_config({
        "id": "cam_disabled",
        "name": "Disabled Cam",
        "source": "rtsp://some-cam/feed",
        "enabled": False,
    })
    assert reader is None
    assert cam_mgr.count_total() == 0


def test_camera_with_empty_configured_source_is_ignored():
    """Unconfigured template cameras must not block app-managed camera readiness."""
    cam_mgr = CameraManager()
    reader = cam_mgr.add_camera_from_config({
        "id": "camera_01",
        "name": "Main Entrance",
        "source": "",
        "enabled": True,
    })
    assert reader is None
    assert cam_mgr.count_total() == 0


def test_stream_reader_start_is_idempotent(monkeypatch):
    """Repeated start calls must not create concurrent capture workers."""
    reader = StreamReader(camera_id="cam_idempotent", name="Test", source="unused")
    started = []

    def worker():
        started.append(threading.current_thread())
        while reader._running:
            time.sleep(0.005)

    monkeypatch.setattr(reader, "_run_worker_loop", worker)
    reader.start()
    first_thread = reader._thread
    reader.start()

    assert reader._thread is first_thread
    assert first_thread is not None
    reader.stop()
    assert len(started) == 1
