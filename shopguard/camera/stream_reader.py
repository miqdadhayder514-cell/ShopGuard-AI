import enum
import os
import threading
import time
from typing import Any, Optional, Tuple
import cv2
import numpy as np

from ..utils.logger import get_logger, mask_url

logger = get_logger("camera.stream")


def is_webcam_source(source: Any) -> Tuple[bool, int]:
    """
    Determines if a video source identifier corresponds to a local hardware webcam.
    Supported patterns:
      - Integer index (e.g. 0, 1)
      - Numeric string (e.g. "0", "1")
      - Prefix syntax (e.g. "webcam:0", "webcam:1", "camera:0")
      - Keyword alias (e.g. "webcam", "camera" -> defaults to index 0)
    Returns: (is_webcam: bool, device_index: int)
    """
    if isinstance(source, int):
        return True, source
    if isinstance(source, str):
        s = source.strip()
        if s.isdigit():
            return True, int(s)
        low = s.lower()
        if low.startswith("webcam:") or low.startswith("camera:"):
            parts = low.split(":", 1)
            idx_str = parts[1].strip()
            return True, int(idx_str) if idx_str.isdigit() else 0
        if low in ("webcam", "camera"):
            return True, 0
    return False, -1


def check_webcam_available(device_index: int = 0) -> Tuple[bool, str, Optional[Tuple[int, int]]]:
    """
    Probes whether a webcam at device_index is physically available and can produce frames.
    Returns: (is_available: bool, status_message: str, resolution: Optional[Tuple[width, height]])
    """
    if device_index < 0 or device_index > 15:
        return (
            False,
            f"Webcam device index {device_index} is out of valid range (0-15). "
            "Please specify a valid camera device index.",
            None,
        )

    try:
        # On Windows, try DirectShow first for fast device inquiry
        cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(device_index)

        if not cap.isOpened():
            return (
                False,
                f"Webcam device index {device_index} cannot be opened. "
                "Check that the webcam is connected, enabled in Device Manager, "
                "and allowed under Windows Settings -> Privacy & security -> Camera.",
                None,
            )

        try:
            # Request HD 720p resolution for sharper person detection at a distance
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        except Exception:
            pass

        ret, frame = cap.read()
        if not ret or frame is None or frame.size == 0:
            cap.release()
            return (
                False,
                f"Webcam device index {device_index} opened but failed to capture a frame. "
                "The webcam may be in use by another application (e.g. Teams, Zoom, Skype).",
                None,
            )

        h, w = frame.shape[:2]
        cap.release()
        return True, f"Webcam index {device_index} is available (Resolution: {w}x{h}).", (w, h)
    except Exception as e:
        return False, f"Exception while probing webcam index {device_index}: {e}", None


class CameraStatus(enum.Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"


class StreamReader:
    """
    Threaded, resilient video stream reader supporting RTSP streams, local video files,
    and live laptop/USB webcams.
    Runs a background reading loop to keep frame latency minimal and automatically recovers from
    transient stream drops or network disruptions.
    """

    def __init__(
        self,
        camera_id: str,
        name: str,
        source: Any,
        fps: float = 5.0,
        connection_timeout: float = 10.0,
        reconnect_interval: float = 5.0,
        is_local_file: Optional[bool] = None,
        loop_local_file: bool = True,
    ):
        self.camera_id = camera_id
        self.name = name
        self.source = source
        self.target_fps = max(0.1, float(fps))
        self.connection_timeout = float(connection_timeout)
        self.reconnect_interval = float(reconnect_interval)

        # Detect if source is local webcam, RTSP stream, or local video file
        is_cam, dev_idx = is_webcam_source(self.source)
        self.is_webcam = is_cam
        self.webcam_index = dev_idx

        if self.is_webcam:
            self.is_local_file = False
            self.loop_local_file = False
        elif is_local_file is None:
            self.is_local_file = (
                isinstance(self.source, str)
                and os.path.exists(self.source)
                and not self.source.lower().startswith("rtsp://")
            )
            self.loop_local_file = loop_local_file
        else:
            self.is_local_file = is_local_file
            self.loop_local_file = loop_local_file

        self._status = CameraStatus.DISCONNECTED
        self._last_frame: Optional[np.ndarray] = None
        self._last_frame_time: float = 0.0
        self._last_successful_read_time: float = 0.0
        self._consecutive_failures = 0
        self._total_frames_read = 0

        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._cap: Optional[cv2.VideoCapture] = None

    @property
    def status(self) -> CameraStatus:
        with self._lock:
            return self._status

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._status == CameraStatus.CONNECTED

    @property
    def is_ready(self) -> bool:
        """True only while the capture worker is live and a recent frame is available."""
        with self._lock:
            thread = self._thread
            return bool(
                self._running
                and thread is not None
                and thread.is_alive()
                and self._status == CameraStatus.CONNECTED
                and self._last_frame is not None
                and time.time() - self._last_frame_time <= max(2.0, self.connection_timeout)
            )

    @property
    def last_frame_time(self) -> float:
        with self._lock:
            return self._last_frame_time

    def start(self) -> None:
        """Starts the background stream capture worker."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return

            self._running = True
            self._thread = threading.Thread(
                target=self._worker_loop,
                name=f"CameraWorker-{self.camera_id}",
                daemon=True,
            )
            self._thread.start()
        logger.info(
            f"Started capture worker for camera '{self.name}' (ID: {self.camera_id}, Source: {mask_url(self.source)})"
        )

    def stop(self) -> None:
        """Stops the worker thread and releases OpenCV resources gracefully."""
        with self._lock:
            self._running = False
            thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=3.0)
            if thread.is_alive():
                logger.warning(
                    f"Camera worker for '{self.camera_id}' did not stop within 3 seconds; "
                    "it will release its capture handle when the pending read returns."
                )
        logger.info(f"Stopped capture worker for camera '{self.name}' (ID: {self.camera_id})")

    def read(self) -> Tuple[bool, Optional[np.ndarray], float]:
        """
        Retrieves the latest available frame and timestamp in a thread-safe manner.
        Returns: (success: bool, frame: Optional[np.ndarray], timestamp: float)
        """
        with self._lock:
            if self._last_frame is None or self._status != CameraStatus.CONNECTED:
                return False, None, self._last_frame_time
            # Return copy to prevent concurrent modification
            return True, self._last_frame.copy(), self._last_frame_time

    def _open_capture(self) -> bool:
        """Attempts to open OpenCV VideoCapture for the configured source."""
        self._release_capture()
        masked = mask_url(self.source)

        with self._lock:
            self._status = (
                CameraStatus.CONNECTING
                if self._status == CameraStatus.DISCONNECTED
                else CameraStatus.RECONNECTING
            )

        if not self.source or (isinstance(self.source, str) and not self.source.strip()):
            logger.error(
                f"Video source for camera '{self.camera_id}' is empty or undefined. "
                "If using an environment variable (e.g. 'ENV:CAMERA_01_URL'), verify that "
                "it is defined in your '.env' file or system environment. "
                "To test using your laptop webcam instead, run with '--webcam' or use 'tools/test_webcam.py'."
            )
            with self._lock:
                self._status = CameraStatus.ERROR
            return False

        logger.info(f"Opening video source for camera '{self.camera_id}': {masked}")

        # 1. Handle Local Hardware Webcam Source
        if self.is_webcam:
            if self.webcam_index < 0 or self.webcam_index > 15:
                logger.error(
                    f"Invalid webcam device index {self.webcam_index} for camera '{self.camera_id}'. "
                    "Supported hardware camera index range is 0 to 15."
                )
                with self._lock:
                    self._status = CameraStatus.ERROR
                return False

            try:
                # On Windows, try DirectShow (cv2.CAP_DSHOW) first for fast, non-blocking device initialization
                cap = cv2.VideoCapture(self.webcam_index, cv2.CAP_DSHOW)
                if not cap.isOpened():
                    cap = cv2.VideoCapture(self.webcam_index)

                if not cap.isOpened():
                    logger.error(
                        f"Cannot open webcam device index {self.webcam_index} for camera '{self.camera_id}'. "
                        "Please verify the webcam is connected, not disabled in Windows Device Manager, "
                        "allowed in Windows Privacy Settings, and not in use by another application."
                    )
                    with self._lock:
                        self._status = CameraStatus.ERROR
                    return False

                try:
                    # Request HD 720p resolution for sharper distant person detection
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception:
                    pass

                ret, test_frame = cap.read()
                if not ret or test_frame is None or test_frame.size == 0:
                    logger.error(f"Webcam index {self.webcam_index} opened but returned no frames.")
                    cap.release()
                    with self._lock:
                        self._status = CameraStatus.ERROR
                    return False

                self._cap = cap
                with self._lock:
                    self._status = CameraStatus.CONNECTED
                    self._last_successful_read_time = time.time()
                    self._consecutive_failures = 0

                h, w = test_frame.shape[:2]
                logger.info(
                    f"Webcam '{self.camera_id}' (device {self.webcam_index}) connected successfully (Resolution: {w}x{h})."
                )
                return True

            except Exception as e:
                logger.error(f"Exception opening webcam {self.webcam_index} for '{self.camera_id}': {e}")
                with self._lock:
                    self._status = CameraStatus.ERROR
                return False

        # 2. Handle RTSP Stream Source
        is_rtsp = isinstance(self.source, str) and self.source.lower().startswith("rtsp://")
        if is_rtsp:
            try:
                from urllib.parse import urlparse
                import socket
                parsed = urlparse(self.source)
                host = parsed.hostname
                port = parsed.port or 554
                if host:
                    sock = socket.create_connection((host, port), timeout=min(2.0, self.connection_timeout))
                    sock.close()
            except Exception as e:
                logger.warning(f"RTSP stream '{self.camera_id}' ({masked}) host unreachable: {e}")
                with self._lock:
                    self._status = CameraStatus.ERROR
                return False

        # 3. Handle RTSP & Local File Video Capture
        try:
            if is_rtsp:
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

            cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                # Fallback to default backend
                cap = cv2.VideoCapture(self.source)

            if not cap.isOpened():
                logger.warning(f"Failed to open video source for camera '{self.camera_id}': {masked}")
                with self._lock:
                    self._status = CameraStatus.ERROR
                return False

            # Set small buffer to prevent stale video frames and configure timeouts
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                timeout_ms = int(self.connection_timeout * 1000)
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms)
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms)
            except Exception:
                pass

            self._cap = cap
            with self._lock:
                self._status = CameraStatus.CONNECTED
                self._last_successful_read_time = time.time()
                self._consecutive_failures = 0

            logger.info(f"Camera '{self.camera_id}' connected successfully.")
            return True

        except Exception as e:
            logger.error(f"Exception opening camera '{self.camera_id}' ({masked}): {e}")
            with self._lock:
                self._status = CameraStatus.ERROR
            return False

    def _release_capture(self) -> None:
        """Releases the underlying cv2.VideoCapture handle safely."""
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception as e:
                logger.debug(f"Error releasing VideoCapture for '{self.camera_id}': {e}")
            self._cap = None

    def _worker_loop(self) -> None:
        try:
            self._run_worker_loop()
        finally:
            self._release_capture()
            with self._lock:
                self._status = CameraStatus.DISCONNECTED

    def _run_worker_loop(self) -> None:
        """Continuous background loop reading frames, handling timeouts and reconnects."""
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                success = self._open_capture()
                if not success:
                    time.sleep(self.reconnect_interval)
                    continue

            # Read frame
            try:
                grabbed, frame = self._cap.read()
            except Exception as e:
                logger.warning(f"Error during cap.read() on '{self.camera_id}': {e}")
                grabbed, frame = False, None

            now = time.time()

            if grabbed and frame is not None and frame.size > 0:
                with self._lock:
                    if not self._running:
                        break
                    self._last_frame = frame
                    self._last_frame_time = now
                    self._last_successful_read_time = now
                    self._status = CameraStatus.CONNECTED
                    self._consecutive_failures = 0
                    self._total_frames_read += 1

                # Frame rate throttling for reading
                sleep_duration = 1.0 / (self.target_fps * 2.0)
                time.sleep(max(0.001, sleep_duration))

            else:
                # Frame read failed or EOF
                if self.is_local_file and self.loop_local_file:
                    # Loop video file from beginning for continuous simulation
                    try:
                        self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        time.sleep(0.05)
                        continue
                    except Exception:
                        pass

                with self._lock:
                    self._consecutive_failures += 1

                # Check connection timeout
                silence_duration = now - self._last_successful_read_time
                if silence_duration > self.connection_timeout:
                    masked = mask_url(self.source)
                    logger.warning(
                        f"Camera '{self.camera_id}' ({masked}) timed out (no frame for {silence_duration:.1f}s). Reconnecting..."
                    )
                    with self._lock:
                        self._status = CameraStatus.RECONNECTING
                    self._release_capture()
                    time.sleep(self.reconnect_interval)
                else:
                    time.sleep(0.1)
