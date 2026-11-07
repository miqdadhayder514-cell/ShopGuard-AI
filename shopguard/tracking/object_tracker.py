from collections import deque
from dataclasses import dataclass, field
import time
from typing import Deque, Dict, List, Optional, Tuple
from ..detection.person_detector import Detection
from ..utils.logger import get_logger

logger = get_logger("tracking")


@dataclass
class TrackInfo:
    """Historical and state tracking metadata for a single tracked person."""
    track_id: int
    first_seen: float
    last_seen: float
    latest_bbox: Tuple[int, int, int, int]
    latest_confidence: float
    positions: Deque[Tuple[float, float]] = field(default_factory=lambda: deque(maxlen=40))

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.last_seen - self.first_seen)


class ObjectTracker:
    """
    Maintains track history, position trajectories, and lifecycle for tracked persons.
    Handles track persistence and automatic garbage collection of expired tracks.
    """

    def __init__(self, track_expiry_seconds: float = 8.0):
        self.track_expiry_seconds = float(track_expiry_seconds)
        self.tracks: Dict[int, TrackInfo] = {}

    def update(self, detections: List[Detection], timestamp: Optional[float] = None) -> None:
        """Updates internal track states from the latest frame detections."""
        now = timestamp if timestamp is not None else time.time()
        seen_track_ids = set()

        for det in detections:
            if det.track_id is None:
                continue

            tid = det.track_id
            seen_track_ids.add(tid)
            cx, cy = det.bottom_center

            if tid not in self.tracks:
                track = TrackInfo(
                    track_id=tid,
                    first_seen=now,
                    last_seen=now,
                    latest_bbox=det.bbox,
                    latest_confidence=det.confidence,
                )
                track.positions.append((cx, cy))
                self.tracks[tid] = track
            else:
                track = self.tracks[tid]
                track.last_seen = now
                track.latest_bbox = det.bbox
                track.latest_confidence = det.confidence
                track.positions.append((cx, cy))

        # Cleanup expired tracks
        self.cleanup_expired(now)

    def cleanup_expired(self, current_time: Optional[float] = None) -> None:
        """Removes tracks that haven't been observed within track_expiry_seconds."""
        now = current_time if current_time is not None else time.time()
        expired_ids = [
            tid for tid, info in self.tracks.items()
            if (now - info.last_seen) > self.track_expiry_seconds
        ]
        for tid in expired_ids:
            del self.tracks[tid]

    def get_track(self, track_id: int) -> Optional[TrackInfo]:
        """Returns track info for a specific ID."""
        return self.tracks.get(track_id)

    def reset(self) -> None:
        """Clears all active tracks and trajectories."""
        self.tracks.clear()

    def get_all_active_tracks(self) -> List[TrackInfo]:
        """Returns list of currently active tracks."""
        return list(self.tracks.values())

    def get_recently_lost_tracks(self, threshold_seconds: float = 2.0, current_time: Optional[float] = None) -> List[int]:
        """Returns list of track IDs that were not observed in the last threshold_seconds."""
        now = current_time if current_time is not None else time.time()
        lost = []
        for tid, track in self.tracks.items():
            if 0 < (now - track.last_seen) <= self.track_expiry_seconds and (now - track.last_seen) >= threshold_seconds:
                lost.append(tid)
        return lost
