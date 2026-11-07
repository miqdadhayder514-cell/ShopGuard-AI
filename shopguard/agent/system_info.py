"""
ShopGuard AI - Host System Information & Diagnostics
Retrieves Windows environment metrics, memory statistics, uptime, and incident storage metrics.
"""

import os
import platform
import sys
import time
from typing import Dict, Any

from ..utils.helpers import check_disk_space

_AGENT_START_TIME = time.time()


def get_agent_uptime_seconds() -> float:
    """Returns the continuous uptime of the Local Security Agent process in seconds."""
    return max(0.0, time.time() - _AGENT_START_TIME)


def get_process_memory_mb() -> float:
    """Estimates process memory usage in MB using standard library or Windows APIs."""
    try:
        import resource
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 1)
    except Exception:
        pass

    # Windows fallback
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return round(counters.WorkingSetSize / (1024.0 * 1024.0), 1)
    except Exception:
        pass

    return 0.0


def count_recorded_incidents(incident_dir: str = "data/incidents") -> int:
    """Counts valid incident metadata files in the local incidents folder."""
    if not os.path.isdir(incident_dir):
        return 0
    count = 0
    try:
        for root, _, files in os.walk(incident_dir):
            for f in files:
                if f.endswith(".json"):
                    count += 1
    except Exception:
        return 0
    return count


def collect_system_info(api_host: str, api_port: int, auth_enabled: bool = True) -> Dict[str, Any]:
    """Collects comprehensive diagnostic metrics on host platform and runtime."""
    return {
        "service_name": "ShopGuard AI Local Security Agent",
        "version": "2.0.0",
        "operating_system": f"{platform.system()} {platform.release()} ({platform.version()})",
        "python_version": sys.version.split()[0],
        "uptime_seconds": round(get_agent_uptime_seconds(), 1),
        "cpu_count": os.cpu_count() or 1,
        "process_memory_mb": get_process_memory_mb(),
        "total_incidents_recorded": count_recorded_incidents("data/incidents"),
        "api_host": api_host,
        "api_port": api_port,
        "auth_enabled": auth_enabled,
    }
