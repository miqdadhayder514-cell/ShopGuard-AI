from dataclasses import dataclass
import enum
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger("security.controller")


class SecurityState(str, enum.Enum):
    DISARMED = "DISARMED"
    ARMING = "ARMING"
    ARMED = "ARMED"
    PARTIAL = "PARTIAL"
    OFFLINE = "OFFLINE"


@dataclass
class ArmCheckResult:
    """Detailed results of the pre-arming validation checks."""
    can_arm: bool
    reasons: List[str]
    has_connected_camera: bool
    ai_model_loaded: bool
    has_valid_zones: bool
    processing_running: bool


class SecurityController:
    """
    Thread-safe manual security state machine for ShopGuard AI.
    Controls transitions between DISARMED, ARMING, ARMED, PARTIAL, and OFFLINE.
    Ensures strict validation before granting armed status.
    """

    def __init__(self, initial_state: SecurityState = SecurityState.DISARMED):
        self._state = initial_state
        self._lock = threading.RLock()
        self._state_listeners: List[Callable[[SecurityState, SecurityState], None]] = []

        # Dependencies checked during arming
        self._camera_manager = None
        self._person_detector = None
        self._zone_manager = None
        self._is_processing_active: Callable[[], bool] = lambda: False
        self._is_processing_worker_active: Callable[[], bool] = lambda: False

    def bind_dependencies(
        self,
        camera_manager,
        person_detector,
        zone_manager,
        is_processing_active: Optional[Callable[[], bool]] = None,
        is_processing_worker_active: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Binds system components required for arming verification."""
        with self._lock:
            self._camera_manager = camera_manager
            self._person_detector = person_detector
            self._zone_manager = zone_manager
            if is_processing_active:
                self._is_processing_active = is_processing_active
            if is_processing_worker_active:
                self._is_processing_worker_active = is_processing_worker_active
            else:
                self._is_processing_worker_active = self._is_processing_active

    @property
    def state(self) -> SecurityState:
        with self._lock:
            return self._state

    @property
    def is_armed(self) -> bool:
        """Returns True if the system is actively monitoring (ARMED or PARTIAL)."""
        with self._lock:
            return self._state in (SecurityState.ARMED, SecurityState.PARTIAL)

    def add_state_listener(self, listener: Callable[[SecurityState, SecurityState], None]) -> None:
        """Registers a callback for state transition notifications."""
        with self._lock:
            self._state_listeners.append(listener)

    def _set_state(self, new_state: SecurityState) -> None:
        """Internal transition with notification dispatch."""
        with self._lock:
            old_state = self._state
            if old_state == new_state:
                return
            self._state = new_state
            logger.info(f"Security state changed: {old_state.value} -> {new_state.value}")
            listeners = list(self._state_listeners)

        for cb in listeners:
            try:
                cb(old_state, new_state)
            except Exception as e:
                logger.error(f"Error in state transition listener: {e}")

    def verify_arming_prerequisites(self) -> ArmCheckResult:
        """
        Executes required security checks before switching to ARMED:
        1. Every enabled camera is connected and producing fresh frames.
        2. AI model is loaded and functional.
        3. Enabled cameras have valid configured zones.
        4. Camera processing pipeline is running.
        """
        reasons: List[str] = []

        # 1. Every enabled camera must be actively producing fresh frames.
        has_cam = False
        if self._camera_manager:
            total_cams = self._camera_manager.count_total()
            conn_cams = self._camera_manager.count_connected()
            readiness_counter = getattr(type(self._camera_manager), "count_ready", None)
            ready_cams = self._camera_manager.count_ready() if callable(readiness_counter) else conn_cams
            if total_cams == 0:
                reasons.append("No cameras are configured or enabled in the system.")
            elif ready_cams != total_cams:
                if conn_cams == 0:
                    reasons.append("None of the enabled cameras are currently connected.")
                get_statuses = getattr(type(self._camera_manager), "get_statuses", None)
                camera_status = self._camera_manager.get_statuses() if callable(get_statuses) else {}
                unavailable = []
                if isinstance(camera_status, dict):
                    unavailable = [
                        f"{camera_id} ({details.get('status', 'UNKNOWN')})"
                        for camera_id, details in camera_status.items()
                        if not details.get("is_ready", details.get("is_connected", False))
                    ]
                reasons.append(
                    f"All enabled cameras must be connected and producing fresh frames "
                    f"before arming ({ready_cams}/{total_cams} ready; "
                    f"{conn_cams}/{total_cams} connected). Unready cameras: "
                    f"{', '.join(unavailable) or 'camera readiness unavailable'}."
                )
            else:
                has_cam = True
        else:
            reasons.append("Camera manager is not bound to the security controller.")

        # 2. AI model loaded check
        ai_loaded = False
        if self._person_detector:
            if self._person_detector.is_loaded:
                ai_loaded = True
            else:
                err = self._person_detector.load_error or "Model weights missing or initialization failed."
                reasons.append(f"AI detection model is not loaded: {err}")
        else:
            reasons.append("AI person detector is not bound to the security controller.")

        # 3. Valid zones configured for enabled cameras check
        has_zones = False
        if self._zone_manager and self._camera_manager:
            cameras = self._camera_manager.get_all_cameras()
            missing_zone_cams = []
            for cam_id in cameras.keys():
                if not self._zone_manager.has_enabled_zones(cam_id):
                    missing_zone_cams.append(cam_id)

            if not missing_zone_cams and cameras:
                has_zones = True
            else:
                reasons.append(
                    "No valid protected zones are configured for every enabled camera. "
                    "Each enabled camera must have at least one enabled restricted zone. "
                    f"Missing zones for cameras: {missing_zone_cams or list(cameras.keys())}"
                )
        else:
            reasons.append("Zone manager or camera manager is not configured.")

        # 4. Processing pipeline active check
        processing_running = False
        try:
            processing_running = bool(self._is_processing_active())
            if not processing_running:
                reasons.append("Camera processing engine is not active.")
        except Exception as e:
            reasons.append(f"Error checking processing state: {e}")

        can_arm = has_cam and ai_loaded and has_zones and processing_running
        return ArmCheckResult(
            can_arm=can_arm,
            reasons=reasons,
            has_connected_camera=has_cam,
            ai_model_loaded=ai_loaded,
            has_valid_zones=has_zones,
            processing_running=processing_running,
        )

    def arm(self) -> Tuple[bool, str, Optional[ArmCheckResult]]:
        """
        Attempts to arm the security system.
        Follows the 8-step verification procedure:
        1. Change state to ARMING.
        2. Run prerequisites check.
        3. Switch to ARMED if all pass.
        4. If checks fail, return to DISARMED with precise reasons.
        """
        with self._lock:
            if self._state != SecurityState.DISARMED:
                result = self.verify_arming_prerequisites()
                return False, f"Security system is already {self._state.value}.", result

            logger.info("Arming command received. Initiating system checks...")
            self._set_state(SecurityState.ARMING)

            result = self.verify_arming_prerequisites()
            if result.can_arm:
                # Recheck at the transition boundary so an unavailable feed is never
                # reported as a successful full-coverage arm.
                final_result = self.verify_arming_prerequisites()
                if final_result.can_arm:
                    self._set_state(SecurityState.ARMED)
                    msg = "Security system successfully ARMED. All cameras and protected zones are active."
                    logger.info(msg)
                    return True, msg, final_result
                result = final_result

            self._set_state(SecurityState.DISARMED)
            failure_msg = "Arming rejected: " + "; ".join(result.reasons)
            logger.warning(failure_msg)
            return False, failure_msg, result

    def disarm(self) -> Tuple[bool, str]:
        """
        Disarms the security system.
        Stops intrusion alerts while keeping camera feeds and health monitoring active.
        """
        with self._lock:
            self._set_state(SecurityState.DISARMED)
            msg = "System DISARMED. Intrusion detection paused. Camera feeds remain active."
            logger.info(msg)
            return True, msg

    def evaluate_intrusions(self, intrusion_detector: Any, **frame_data: Any) -> List[Any]:
        """Serialize intrusion evaluation with disarm so no new evaluation starts after disarm returns."""
        with self._lock:
            frame_data["is_armed"] = self._state in (
                SecurityState.ARMED,
                SecurityState.PARTIAL,
            )
            return intrusion_detector.process_frame_detections(**frame_data)

    def monitoring_failed(self, reason: str) -> None:
        """Mark monitoring offline when the processing worker exits unexpectedly."""
        with self._lock:
            logger.error(f"Security monitoring is unavailable: {reason}")
            self._set_state(SecurityState.OFFLINE)

    def update_camera_health(self) -> None:
        """
        Updates security state based on live camera connectivity:
        - If ARMED and an enabled camera drops -> switches to PARTIAL.
        - If ARMED/PARTIAL and all cameras drop -> switches to OFFLINE.
        - If PARTIAL and all cameras recover -> switches to ARMED.
        - If OFFLINE and cameras recover -> switches back to ARMED or PARTIAL.
        - Does nothing if DISARMED.
        """
        with self._lock:
            if self._state not in (SecurityState.ARMED, SecurityState.PARTIAL, SecurityState.OFFLINE):
                return

            if not self._camera_manager:
                return

            try:
                processing_active = bool(self._is_processing_worker_active())
            except Exception as exc:
                logger.error(f"Could not verify the camera processing worker: {exc}")
                processing_active = False
            if not processing_active:
                if self._state != SecurityState.OFFLINE:
                    logger.warning("Camera processing worker is unavailable. System state degraded to OFFLINE.")
                    self._set_state(SecurityState.OFFLINE)
                return

            total = self._camera_manager.count_total()
            readiness_counter = getattr(type(self._camera_manager), "count_ready", None)
            connected = (
                self._camera_manager.count_ready()
                if callable(readiness_counter)
                else self._camera_manager.count_connected()
            )

            if total == 0 or connected == 0:
                if self._state != SecurityState.OFFLINE:
                    logger.warning("All camera feeds are disconnected. System state degraded to OFFLINE.")
                    self._set_state(SecurityState.OFFLINE)
            elif connected < total:
                if self._state != SecurityState.PARTIAL:
                    logger.warning(f"Camera feed failure ({connected}/{total} online). State set to PARTIAL.")
                    self._set_state(SecurityState.PARTIAL)
            else:
                # All connected
                if self._state in (SecurityState.PARTIAL, SecurityState.OFFLINE):
                    logger.info("All camera feeds restored. System state restored to full ARMED.")
                    self._set_state(SecurityState.ARMED)
