from collections import deque
import threading
import time
from typing import Deque, List, Optional, Tuple
import numpy as np


class VideoBuffer:
    """
    Thread-safe rolling circular in-memory buffer for video frames.
    Stores recent video history to support pre-event incident clipping.
    """

    def __init__(self, buffer_seconds: float = 10.0, fps: float = 5.0):
        self.buffer_seconds = max(1.0, float(buffer_seconds))
        self.fps = max(1.0, float(fps))
        self.maxlen = int(self.buffer_seconds * self.fps * 2.0)

        self._buffer: Deque[Tuple[np.ndarray, float]] = deque(maxlen=self.maxlen)
        self._lock = threading.Lock()

    def append(self, frame: np.ndarray, timestamp: Optional[float] = None) -> None:
        """Appends a frame with its timestamp to the rolling buffer."""
        if frame is None or frame.size == 0:
            return

        ts = timestamp if timestamp is not None else time.time()
        with self._lock:
            # We copy or store frame
            self._buffer.append((frame.copy(), ts))

            # Discard frames older than buffer_seconds
            cutoff = ts - self.buffer_seconds
            while self._buffer and self._buffer[0][1] < cutoff:
                self._buffer.popleft()

    def get_frames(self, start_timestamp: Optional[float] = None) -> List[Tuple[np.ndarray, float]]:
        """
        Retrieves frames from the buffer.
        If start_timestamp is provided, retrieves frames with timestamp >= start_timestamp.
        """
        with self._lock:
            if not self._buffer:
                return []

            if start_timestamp is None:
                return list(self._buffer)

            return [(f.copy(), t) for f, t in self._buffer if t >= start_timestamp]

    def clear(self) -> None:
        """Clears all buffered frames."""
        with self._lock:
            self._buffer.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)
