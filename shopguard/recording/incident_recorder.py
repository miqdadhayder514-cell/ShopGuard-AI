from dataclasses import dataclass, asdict
from datetime import datetime
import json
import os
import queue
import threading
import time
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np

from ..intrusion.intrusion_detector import IntrusionEvent
from ..utils.logger import get_logger

logger = get_logger("recording.incident")


@dataclass
class IncidentMetadata:
    """Standardized metadata structure saved alongside incident video clips."""
    incident_id: str
    camera_id: str
    camera_name: str
    event_type: str
    event_timestamp: str  # ISO 8601
    track_id: Optional[int]
    detection_confidence: float
    confidence: float
    zone_id: str
    zone_name: str
    video_filename: str
    review_status: str = "UNREVIEWED"
    duration_seconds: float = 0.0
    total_frames: int = 0
    source_type: str = "live_cctv"
    simulation_mode: bool = False
    rtsp_verified: bool = False


class ActiveRecordingSession:
    """Manages collection of pre-event and post-event frames for an ongoing incident."""

    def __init__(
        self,
        event: IntrusionEvent,
        camera_name: str,
        pre_frames: List[Tuple[np.ndarray, float]],
        post_event_seconds: float,
        output_dir: str,
        fps: float = 5.0,
        source_type: str = "live_cctv",
        simulation_mode: bool = False,
        rtsp_verified: bool = False,
    ):
        self.event = event
        self.camera_name = camera_name
        self.post_event_seconds = post_event_seconds
        self.output_dir = output_dir
        self.fps = fps
        self.source_type = source_type
        self.simulation_mode = simulation_mode
        self.rtsp_verified = rtsp_verified
        self.target_end_time = event.timestamp + post_event_seconds

        # Store frames as (frame, timestamp)
        self.frames: List[Tuple[np.ndarray, float]] = list(pre_frames)
        self.is_completed = False

    def add_frame(self, frame: np.ndarray, timestamp: float) -> bool:
        """Adds a post-event frame. Returns True if recording session is complete."""
        if self.is_completed:
            return True

        self.frames.append((frame.copy(), timestamp))
        if timestamp >= self.target_end_time:
            self.is_completed = True
            return True
        return False


class IncidentRecorder:
    """
    Manages incident video compilation and persistence.
    Combines pre-event buffer history with post-event footage and generates JSON metadata.
    """

    def __init__(
        self,
        output_directory: str = "data/incidents",
        pre_event_seconds: float = 10.0,
        post_event_seconds: float = 15.0,
        fps: float = 5.0,
        enabled: bool = True,
    ):
        self.output_directory = output_directory
        self.pre_event_seconds = float(pre_event_seconds)
        self.post_event_seconds = float(post_event_seconds)
        self.fps = max(1.0, float(fps))
        self.enabled = enabled

        self._active_sessions: List[ActiveRecordingSession] = []
        self._lock = threading.Lock()
        self._write_queue: queue.Queue = queue.Queue(maxsize=100)
        self._worker_running = True
        self._worker_thread = threading.Thread(
            target=self._writer_worker,
            name="IncidentWriterWorker",
            daemon=True,
        )
        self._worker_thread.start()

    def trigger_incident(
        self,
        event: IntrusionEvent,
        camera_name: str,
        pre_frames: List[Tuple[np.ndarray, float]],
        source_type: str = "live_cctv",
        simulation_mode: bool = False,
        rtsp_verified: bool = False,
    ) -> None:
        """Starts an incident recording session upon an intrusion event."""
        if not self.enabled:
            logger.debug("Incident recording is disabled in configuration. Skipping clip recording.")
            return

        with self._lock:
            # Check for existing active session for same camera and track_id
            for session in self._active_sessions:
                if (
                    session.event.camera_id == event.camera_id
                    and session.event.track_id == event.track_id
                    and not session.is_completed
                ):
                    logger.debug(f"Incident recording already active for track {event.track_id} on {event.camera_id}")
                    return

            logger.info(
                f"Starting incident recording for {event.camera_id} "
                f"(Event: {event.event_type.value}, Pre-frames: {len(pre_frames)}, Source: {source_type})"
            )
            session = ActiveRecordingSession(
                event=event,
                camera_name=camera_name,
                pre_frames=pre_frames,
                post_event_seconds=self.post_event_seconds,
                output_dir=self.output_directory,
                fps=self.fps,
                source_type=source_type,
                simulation_mode=simulation_mode,
                rtsp_verified=rtsp_verified,
            )
            self._active_sessions.append(session)

    def on_new_frame(self, camera_id: str, frame: np.ndarray, timestamp: float) -> None:
        """Feeds newly arrived frames to all active recording sessions for the camera."""
        if not self.enabled or frame is None:
            return

        completed_sessions = []
        with self._lock:
            for session in self._active_sessions:
                if session.event.camera_id == camera_id and not session.is_completed:
                    is_done = session.add_frame(frame, timestamp)
                    if is_done:
                        completed_sessions.append(session)

            for s in completed_sessions:
                self._active_sessions.remove(s)
                self._write_queue.put(s)

    def _writer_worker(self) -> None:
        """Background worker consuming completed sessions and persisting video & JSON."""
        while self._worker_running or not self._write_queue.empty():
            try:
                session: ActiveRecordingSession = self._write_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                self._save_session(session)
            except Exception as e:
                logger.error(f"Error persisting incident recording: {e}", exc_info=True)
            finally:
                self._write_queue.task_done()

    def _save_session(self, session: ActiveRecordingSession) -> Optional[Tuple[str, str]]:
        """Writes video file (.mp4) and metadata (.json) to disk."""
        if not session.frames:
            logger.warning(f"No frames captured for incident {session.event.event_id}. Skipping file write.")
            return None

        event = session.event
        dt = datetime.fromtimestamp(event.timestamp)
        date_folder = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%Y%m%d_%H%M%S")

        cam_dir = os.path.join(self.output_directory, date_folder, event.camera_id)
        os.makedirs(cam_dir, exist_ok=True)

        video_filename = f"incident_{time_str}.mp4"
        json_filename = f"incident_{time_str}.json"
        video_path = os.path.join(cam_dir, video_filename)
        json_path = os.path.join(cam_dir, json_filename)

        # Write video using OpenCV VideoWriter
        first_frame = session.frames[0][0]
        h, w = first_frame.shape[:2]

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(video_path, fourcc, session.fps, (w, h))

        if not writer.isOpened():
            # Fallback codec
            fourcc = cv2.VideoWriter_fourcc(*"XVID")
            video_path = video_path.replace(".mp4", ".avi")
            video_filename = video_filename.replace(".mp4", ".avi")
            writer = cv2.VideoWriter(video_path, fourcc, session.fps, (w, h))

        if not writer.isOpened():
            logger.error(f"Failed to initialize VideoWriter for {video_path}")
            return None

        try:
            for frame, _ in session.frames:
                # Resize if needed
                if frame.shape[:2] != (h, w):
                    frame = cv2.resize(frame, (w, h))
                writer.write(frame)
        finally:
            writer.release()

        # Compute duration
        duration = 0.0
        if len(session.frames) >= 2:
            duration = max(0.0, session.frames[-1][1] - session.frames[0][1])

        # Write metadata JSON
        metadata = IncidentMetadata(
            incident_id=event.event_id,
            camera_id=event.camera_id,
            camera_name=session.camera_name,
            event_type=event.event_type.value,
            event_timestamp=dt.isoformat(),
            track_id=event.track_id,
            detection_confidence=event.confidence,
            confidence=event.confidence,
            zone_id=event.zone_id,
            zone_name=event.zone_name,
            video_filename=video_filename,
            review_status="UNREVIEWED",
            duration_seconds=round(duration, 2),
            total_frames=len(session.frames),
            source_type=session.source_type,
            simulation_mode=session.simulation_mode,
            rtsp_verified=session.rtsp_verified,
        )

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(asdict(metadata), f, indent=2)

        logger.info(
            f"Incident successfully saved: {video_path} (Frames: {len(session.frames)}, Duration: {duration:.1f}s)"
        )
        return video_path, json_path

    def shutdown(self) -> None:
        """Flushes active sessions and shuts down the background writer."""
        logger.info("Shutting down incident recorder and finalizing active sessions...")
        with self._lock:
            # Enqueue all active sessions even if incomplete
            for session in self._active_sessions:
                session.is_completed = True
                self._write_queue.put(session)
            self._active_sessions.clear()

        self._worker_running = False
        self._write_queue.join()
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
