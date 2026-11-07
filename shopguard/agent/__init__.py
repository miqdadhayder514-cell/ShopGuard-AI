"""
ShopGuard AI - Phase 2 Local Security Agent Package
"""

from .server import create_app
from .security_auth import auth_manager, require_control_auth
from .state_store import PersistentStateStore
from .system_info import collect_system_info

__all__ = [
    "create_app",
    "auth_manager",
    "require_control_auth",
    "PersistentStateStore",
    "collect_system_info",
]
