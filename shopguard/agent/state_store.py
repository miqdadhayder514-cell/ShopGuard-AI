"""
ShopGuard AI - Persistent Security State Store
Tracks security state transitions, audits clean shutdowns vs unexpected crashes,
and guarantees safe DISARMED default initialization on application startup.
"""

from datetime import datetime, timezone
import json
import os
import threading
import time
from typing import Any, Dict, Optional

from ..security.security_controller import SecurityState
from ..utils.logger import get_logger

logger = get_logger("agent.state")

DEFAULT_STATE_FILE = "data/security_state.json"


class PersistentStateStore:
    """
    Persists security state machine metadata to disk.
    Enforces safe startup in DISARMED mode and audits recovery after process crashes.
    """

    def __init__(self, file_path: str = DEFAULT_STATE_FILE):
        self.file_path = os.path.abspath(file_path)
        self._lock = threading.Lock()
        self.last_clean_shutdown = True
        self.previous_unclean_state: Optional[str] = None

        self._initialize_on_startup()

    def _initialize_on_startup(self) -> None:
        """
        Loads prior state file on startup.
        Inspects if previous run terminated cleanly or crashed.
        Guarantees startup in DISARMED mode.
        """
        with self._lock:
            if os.path.isfile(self.file_path):
                try:
                    with open(self.file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    was_clean = data.get("clean_shutdown", True)
                    prior_state = data.get("state", "DISARMED")

                    if not was_clean and prior_state in ("ARMED", "PARTIAL"):
                        self.last_clean_shutdown = False
                        self.previous_unclean_state = prior_state
                        logger.warning(
                            f"[CRASH RECOVERY] Previous session terminated unexpectedly while in '{prior_state}' state! "
                            "Safely initializing agent in DISARMED mode for operator safety."
                        )
                    else:
                        logger.info(f"Prior session state was '{prior_state}' (Clean shutdown: {was_clean}).")

                except Exception as e:
                    logger.error(f"Error parsing prior state file '{self.file_path}': {e}")

            # Record fresh startup in DISARMED state
            self._save_state_disk(
                state="DISARMED",
                reason="Fresh process startup (Safe default)",
                clean_shutdown=False,  # Set false during active run; flagged true on clean exit
            )

    def record_transition(self, new_state: SecurityState, reason: str = "") -> None:
        """Records a state change event to the persistent storage file."""
        with self._lock:
            self._save_state_disk(
                state=new_state.value,
                reason=reason,
                clean_shutdown=False,
            )

    def record_clean_shutdown(self, current_state: SecurityState) -> None:
        """Marks the session as cleanly terminated on graceful shutdown."""
        with self._lock:
            self._save_state_disk(
                state=current_state.value,
                reason="Graceful agent shutdown",
                clean_shutdown=True,
            )
            logger.info("Security state store marked as cleanly shutdown.")

    def _save_state_disk(self, state: str, reason: str, clean_shutdown: bool) -> None:
        """Internal disk writer."""
        now = time.time()
        iso_str = datetime.now(timezone.utc).isoformat()
        payload = {
            "state": state,
            "timestamp": now,
            "timestamp_iso": iso_str,
            "reason": reason,
            "clean_shutdown": clean_shutdown,
            "agent_version": "2.0.0",
        }
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            temp_path = self.file_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            os.replace(temp_path, self.file_path)
        except Exception as e:
            logger.error(f"Failed to persist security state to '{self.file_path}': {e}")

    def get_state_summary(self) -> Dict[str, Any]:
        """Returns the recorded state metadata."""
        with self._lock:
            if os.path.isfile(self.file_path):
                try:
                    with open(self.file_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
            return {"state": "DISARMED", "clean_shutdown": True}
