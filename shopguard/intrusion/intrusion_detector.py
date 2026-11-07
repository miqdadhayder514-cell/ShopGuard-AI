from dataclasses import dataclass
import enum
import time
from typing import Dict, List, Optional, Tuple
import uuid

from ..detection.person_detector import Detection
from .zone_manager import Zone
from ..utils.logger import get_logger

logger = get_logger("intrusion.detector")


class EventType(str, enum.Enum):
    PERSON_ENTERED_RESTRICTED_ZONE = "PERSON_ENTERED_RESTRICTED_ZONE"
    PERSON_PRESENT_IN_RESTRICTED_ZONE = "PERSON_PRESENT_IN_RESTRICTED_ZONE"
    POSSIBLE_SUSPICIOUS_ACTIVITY = "POSSIBLE_SUSPICIOUS_ACTIVITY"


@dataclass
class IntrusionEvent:
    """Represents a validated intrusion or suspicious detection event."""
    event_id: str
    camera_id: str
    zone_id: str
    zone_name: str
    event_type: EventType
    track_id: Optional[int]
    confidence: float
    bbox: Tuple[int, int, int, int]
    timestamp: float
    persistence_seconds: float


class IntrusionDetector:
    """
    Core security evaluation engine.
    Applies strict armed-state gating, bottom-center zone containment, track persistence,
    event cooldown, and cautious classification to eliminate transient false positives.
    """

    def __init__(
        self,
        minimum_persistence_seconds: float = 2.0,
        event_cooldown_seconds: float = 30.0,
        confidence_threshold: float = 0.45,
        min_consistent_observations: int = 3,
    ):
        self.minimum_persistence_seconds = float(minimum_persistence_seconds)
        self.event_cooldown_seconds = float(event_cooldown_seconds)
        self.confidence_threshold = float(confidence_threshold)
        self.min_consistent_observations = int(min_consistent_observations)

        # State tracking: (camera_id, zone_id, track_id) -> state dict
        self._occupancy: Dict[Tuple[str, str, int], Dict[str, float]] = {}

        # Cooldown tracking: (camera_id, zone_id, track_id) -> last_event_timestamp
        self._last_event_times: Dict[Tuple[str, str, int], float] = {}

    def process_frame_detections(
        self,
        camera_id: str,
        detections: List[Detection],
        zones: List[Zone],
        frame_width: int,
        frame_height: int,
        is_armed: bool,
        timestamp: Optional[float] = None,
    ) -> List[IntrusionEvent]:
        """
        Evaluates detections against zones.
        Returns generated events if ARMED. If DISARMED, suppresses all incident creation.
        """
        now = timestamp if timestamp is not None else time.time()

        # Rule A: In DISARMED state, never generate intrusion incidents
        if not is_armed:
            self._cleanup_stale_occupancy(now)
            return []

        # Filter enabled zones
        active_zones = [z for z in zones if z.enabled and len(z.polygon) >= 3]
        if not active_zones:
            return []

        events: List[IntrusionEvent] = []
        observed_keys = set()

        for det in detections:
            # Distance-adaptive confidence check:
            # Small/distant bounding boxes (height < 30% of frame) are accepted at scaled threshold
            x1, y1, x2, y2 = det.bbox
            box_h_ratio = max(1, y2 - y1) / float(max(1, frame_height))
            if box_h_ratio < 0.30:
                effective_conf = max(0.18, self.confidence_threshold * 0.65)
            else:
                effective_conf = self.confidence_threshold

            if det.confidence < effective_conf:
                continue

            # Check containment via foot-contact (bottom-center) OR torso/body center
            # Foot contact is primary for high-angle CCTV; center ensures reliable detection on eye-level webcams
            pt_bottom = det.bottom_center_normalized(frame_width, frame_height)
            pt_center = det.center_normalized(frame_width, frame_height)
            track_id = det.track_id if det.track_id is not None else 0

            for zone in active_zones:
                if zone.contains_normalized_point(pt_bottom) or zone.contains_normalized_point(pt_center):
                    key = (camera_id, zone.id, track_id)
                    observed_keys.add(key)

                    if key not in self._occupancy:
                        # First observation in zone
                        self._occupancy[key] = {
                            "first_seen": now,
                            "last_seen": now,
                            "observation_count": 1.0,
                            "triggered_initial": 0.0,
                        }
                    else:
                        entry = self._occupancy[key]
                        entry["last_seen"] = now
                        entry["observation_count"] += 1.0

                    entry = self._occupancy[key]
                    duration = now - entry["first_seen"]
                    obs_count = entry["observation_count"]

                    # Evaluate entry persistence
                    if (
                        duration >= self.minimum_persistence_seconds
                        and obs_count >= self.min_consistent_observations
                    ):
                        # Check cooldown (if key not in _last_event_times, cooldown does not apply)
                        last_event_time = self._last_event_times.get(key, -1e9)
                        if (now - last_event_time) >= self.event_cooldown_seconds:
                            # Determine cautious event classification
                            if entry["triggered_initial"] < 0.5:
                                event_type = EventType.PERSON_ENTERED_RESTRICTED_ZONE
                                entry["triggered_initial"] = 1.0
                            elif duration >= (self.minimum_persistence_seconds * 5.0):
                                event_type = EventType.POSSIBLE_SUSPICIOUS_ACTIVITY
                            else:
                                event_type = EventType.PERSON_PRESENT_IN_RESTRICTED_ZONE

                            evt = IntrusionEvent(
                                event_id=f"evt_{int(now * 1000)}_{uuid.uuid4().hex[:6]}",
                                camera_id=camera_id,
                                zone_id=zone.id,
                                zone_name=zone.name,
                                event_type=event_type,
                                track_id=det.track_id,
                                confidence=round(det.confidence, 4),
                                bbox=det.bbox,
                                timestamp=now,
                                persistence_seconds=round(duration, 2),
                            )
                            events.append(evt)
                            self._last_event_times[key] = now

                            logger.warning(
                                f"SECURITY EVENT: {event_type.value} on {camera_id} in '{zone.name}' "
                                f"(Track ID: {det.track_id}, Conf: {det.confidence:.2f}, Persist: {duration:.1f}s)"
                            )

        # Cleanup tracks that departed from zones
        self._cleanup_stale_occupancy(now, grace_period_seconds=2.0)
        return events

    def _cleanup_stale_occupancy(self, current_time: float, grace_period_seconds: float = 2.0) -> None:
        """Removes tracked entries that have not been seen in the zone recently."""
        stale_keys = [
            k for k, v in self._occupancy.items()
            if (current_time - v["last_seen"]) > grace_period_seconds
        ]
        for k in stale_keys:
            del self._occupancy[k]

    def reset(self) -> None:
        """Clears all internal occupancy and cooldown state."""
        self._occupancy.clear()
        self._last_event_times.clear()
