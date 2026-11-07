from dataclasses import dataclass
import time
from typing import Any, Dict, List, Optional

from ..utils.helpers import check_disk_space
from ..utils.logger import get_logger

logger = get_logger("monitoring.health")


@dataclass
class CameraHealthInfo:
    camera_id: str
    camera_name: str
    is_connected: bool
    status: str
    last_frame_age_seconds: float
    total_frames_read: int
    stream_source_masked: str


@dataclass
class SystemHealthReport:
    timestamp: float
    security_state: str
    ai_model_loaded: bool
    ai_model_path: str
    ai_device: str
    disk_free_gb: float
    disk_total_gb: float
    cameras: List[CameraHealthInfo]
    overall_health: str  # "HEALTHY", "DEGRADED", "CRITICAL"


class HealthMonitor:
    """
    Monitors overall system health, stream liveness, AI engine status, and disk storage.
    Provides diagnostic snapshots and ensures camera outages are clearly distinguished
    from intrusion events.
    """

    def __init__(
        self,
        camera_manager=None,
        person_detector=None,
        security_controller=None,
        storage_path: str = "data/incidents",
    ):
        self.camera_manager = camera_manager
        self.person_detector = person_detector
        self.security_controller = security_controller
        self.storage_path = storage_path

    def get_health_report(self) -> SystemHealthReport:
        """Collects a complete diagnostic health snapshot of the system."""
        now = time.time()

        # Disk space
        disk_info = check_disk_space(self.storage_path)
        disk_free = disk_info.get("free_gb", 0.0)
        disk_total = disk_info.get("total_gb", 0.0)

        # AI model
        ai_loaded = self.person_detector.is_loaded if self.person_detector else False
        ai_model_path = self.person_detector.model_path if self.person_detector else "None"
        ai_device = self.person_detector.device if self.person_detector else "None"

        # Security state
        sec_state = self.security_controller.state.value if self.security_controller else "UNKNOWN"

        # Cameras
        cam_reports: List[CameraHealthInfo] = []
        cams_online = 0
        total_cams = 0

        if self.camera_manager:
            cameras = self.camera_manager.get_all_cameras()
            total_cams = len(cameras)
            for cam_id, reader in cameras.items():
                last_time = reader.last_frame_time
                age = (now - last_time) if last_time > 0 else -1.0
                conn = reader.is_connected
                if conn:
                    cams_online += 1

                cam_reports.append(
                    CameraHealthInfo(
                        camera_id=cam_id,
                        camera_name=reader.name,
                        is_connected=conn,
                        status=reader.status.value,
                        last_frame_age_seconds=round(age, 1),
                        total_frames_read=getattr(reader, "_total_frames_read", 0),
                        stream_source_masked=reader.source,
                    )
                )

        # Overall health assessment
        if not ai_loaded or disk_free < 0.5:
            overall = "CRITICAL"
        elif total_cams > 0 and cams_online == 0:
            overall = "CRITICAL"
        elif cams_online < total_cams or disk_free < 2.0:
            overall = "DEGRADED"
        else:
            overall = "HEALTHY"

        return SystemHealthReport(
            timestamp=now,
            security_state=sec_state,
            ai_model_loaded=ai_loaded,
            ai_model_path=ai_model_path,
            ai_device=ai_device,
            disk_free_gb=disk_free,
            disk_total_gb=disk_total,
            cameras=cam_reports,
            overall_health=overall,
        )

    def print_status_summary(self) -> None:
        """Prints a human-readable health summary to the console."""
        rep = self.get_health_report()
        print("\n" + "=" * 55)
        print("          SHOPGUARD AI - SYSTEM HEALTH STATUS")
        print("=" * 55)
        print(f"Overall Status:       {rep.overall_health}")
        print(f"Security State:       {rep.security_state}")
        print(f"AI Model:             {rep.ai_model_path} [{rep.ai_device.upper()}] (Loaded: {rep.ai_model_loaded})")
        print(f"Disk Storage:         {rep.disk_free_gb:.1f} GB free of {rep.disk_total_gb:.1f} GB")
        print("-" * 55)
        print(f"Connected Cameras:    {sum(1 for c in rep.cameras if c.is_connected)} / {len(rep.cameras)}")
        for cam in rep.cameras:
            status_symbol = "[OK]" if cam.is_connected else "[FAIL]"
            print(f"  * {status_symbol} {cam.camera_name} ({cam.camera_id}): {cam.status} (Last frame: {cam.last_frame_age_seconds}s ago)")
        print("=" * 55 + "\n")
