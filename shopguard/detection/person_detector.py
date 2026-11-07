from dataclasses import dataclass, field
import os
import time
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

from ..utils.logger import get_logger
from ..utils.helpers import detect_compute_device
from .tiled_inference import TiledInferenceEngine

logger = get_logger("detection.person")


@dataclass
class Detection:
    """Represents a single detected person with bounding box, confidence, and tracking info."""
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2) in pixel coordinates
    track_id: Optional[int]
    timestamp: float

    @property
    def height_px(self) -> int:
        """Returns the bounding box height in pixels."""
        return max(1, self.bbox[3] - self.bbox[1])

    @property
    def width_px(self) -> int:
        """Returns the bounding box width in pixels."""
        return max(1, self.bbox[2] - self.bbox[0])

    @property
    def area_px(self) -> int:
        """Returns the bounding box area in pixels."""
        return self.width_px * self.height_px

    @property
    def bottom_center(self) -> Tuple[float, float]:
        """Calculates the bottom-center anchor point (x, y) for zone-containment logic."""
        x1, y1, x2, y2 = self.bbox
        return (float(x1 + x2) / 2.0, float(y2))

    def bottom_center_normalized(self, frame_width: int, frame_height: int) -> Tuple[float, float]:
        """Returns bottom-center point normalized to [0.0, 1.0]."""
        cx, cy = self.bottom_center
        w = max(1, frame_width)
        h = max(1, frame_height)
        return (cx / w, cy / h)

    @property
    def center(self) -> Tuple[float, float]:
        """Calculates the center anchor point (x, y) of the person's bounding box."""
        x1, y1, x2, y2 = self.bbox
        return (float(x1 + x2) / 2.0, float(y1 + y2) / 2.0)

    def center_normalized(self, frame_width: int, frame_height: int) -> Tuple[float, float]:
        """Returns center point normalized to [0.0, 1.0]."""
        cx, cy = self.center
        w = max(1, frame_width)
        h = max(1, frame_height)
        return (cx / w, cy / h)


@dataclass
class RejectedDetection:
    """Audit record for a detected person candidate that was filtered out."""
    bbox: Tuple[int, int, int, int]
    confidence: float
    height_px: int
    width_px: int
    reason: str  # e.g., 'CONFIDENCE_BELOW_THRESHOLD', 'BELOW_MIN_BOX_SIZE'
    effective_threshold: float


@dataclass
class DetectionDiagnostics:
    """Diagnostic metrics captured during inference for monitoring and audit."""
    inference_size: int
    inference_fps: float
    inference_time_ms: float
    total_candidates: int
    accepted_count: int
    rejected_count: int
    rejected_detections: List[RejectedDetection] = field(default_factory=list)
    active_track_ids: List[int] = field(default_factory=list)
    lost_track_ids: List[int] = field(default_factory=list)
    tiled_inference_used: bool = False


class PersonDetector:
    """
    YOLO-based person detection and ByteTrack object tracking engine.
    Supports configurable resolution (640, 960, 1280), aspect-ratio preservation (rect),
    distance-adaptive confidence scaling, minimum bounding box constraints, optional tiled inference,
    and comprehensive diagnostics.
    """

    SUPPORTED_RESOLUTIONS = (640, 960, 1280)

    def __init__(
        self,
        model_path: str = "models/yolo11n.pt",
        confidence_threshold: float = 0.45,
        device: str = "cpu",
        use_tracking: bool = True,
        tracker_type: str = "bytetrack.yaml",
        imgsz: int = 640,
        rect: bool = True,
        min_box_height_px: int = 15,
        min_box_width_px: int = 10,
        enable_tiled_inference: bool = False,
        tiled_grid: Tuple[int, int] = (2, 2),
        tiled_overlap: float = 0.20,
    ):
        self.model_path = model_path
        self.confidence_threshold = float(confidence_threshold)
        self.device = detect_compute_device(device)
        self.use_tracking = use_tracking
        self.tracker_type = tracker_type

        # Multi-resolution inference configuration
        self.imgsz = int(imgsz) if int(imgsz) in self.SUPPORTED_RESOLUTIONS else int(imgsz)
        self.rect = bool(rect)
        self.min_box_height_px = max(1, int(min_box_height_px))
        self.min_box_width_px = max(1, int(min_box_width_px))

        # Tiled / Sliced inference for high-res CCTV
        self.enable_tiled_inference = bool(enable_tiled_inference)
        self.tiler = TiledInferenceEngine(grid=tiled_grid, overlap=tiled_overlap)

        self.model = None
        self._is_loaded = False
        self._load_error: Optional[str] = None

        # Tracking state diagnostics
        self._known_track_ids: set = set()
        self.last_diagnostics: Optional[DetectionDiagnostics] = None

        self._init_model()

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    def _init_model(self) -> None:
        """Loads the Ultralytics YOLO model safely."""
        logger.info(
            f"Initializing YOLO Person Detector (Model: {self.model_path}, Device: {self.device}, "
            f"Inference Size: {self.imgsz}px, Rect: {self.rect}, MinBox: {self.min_box_width_px}x{self.min_box_height_px}px, "
            f"Tiled: {self.enable_tiled_inference})..."
        )

        try:
            from ultralytics import YOLO

            model_dir = os.path.dirname(self.model_path)
            if model_dir and not os.path.exists(model_dir):
                os.makedirs(model_dir, exist_ok=True)

            self.model = YOLO(self.model_path)

            if hasattr(self.model, "names") and self.model.names:
                person_class_name = self.model.names.get(0, "person")
                logger.info(f"YOLO model loaded successfully. Target class [0]: '{person_class_name}'.")

            self._is_loaded = True
            self._load_error = None

        except Exception as e:
            err_msg = f"Failed to initialize YOLO model from '{self.model_path}': {e}"
            logger.error(err_msg)
            self._is_loaded = False
            self._load_error = err_msg

    def detect_and_track(
        self,
        frame: np.ndarray,
        timestamp: Optional[float] = None,
    ) -> List[Detection]:
        """
        Runs person detection and tracking on the input frame.
        Applies resolution scaling, distance-adaptive confidence, minimum box dimensions,
        and records comprehensive diagnostics.
        """
        if not self._is_loaded or self.model is None:
            logger.warning("Inference attempted but AI model is not loaded.")
            return []

        if frame is None or frame.size == 0:
            return []

        t0 = time.time()
        ts = timestamp if timestamp is not None else t0
        h_frame, w_frame = frame.shape[:2]

        # Feed lower candidate threshold into tracker so distant candidates are not pre-filtered
        feed_conf = max(0.12, min(self.confidence_threshold, self.confidence_threshold * 0.55))

        raw_candidates: List[Tuple[Tuple[int, int, int, int], float, Optional[int]]] = []
        tiled_used = False

        try:
            # 1. Tiled Inference Branch (if enabled and frame exceeds base resolution)
            if self.enable_tiled_inference and (w_frame >= 1280 or h_frame >= 720):
                tiled_used = True
                tiles = self.tiler.generate_tiles(frame)
                tile_boxes: List[Tuple[int, int, int, int]] = []
                tile_scores: List[float] = []

                for tile in tiles:
                    results = self.model.predict(
                        source=tile.image,
                        classes=[0],
                        conf=feed_conf,
                        device=self.device,
                        imgsz=self.imgsz,
                        rect=self.rect,
                        verbose=False,
                    )
                    if results and len(results) > 0 and results[0].boxes is not None:
                        boxes = results[0].boxes
                        for i in range(len(boxes)):
                            cls_id = int(boxes.cls[i].item()) if boxes.cls is not None else 0
                            if cls_id != 0:
                                continue
                            conf_val = float(boxes.conf[i].item()) if boxes.conf is not None else 0.0
                            xyxy = boxes.xyxy[i].cpu().numpy().astype(int)
                            # Shift coordinates to global frame
                            gx1 = max(0, int(xyxy[0]) + tile.x_offset)
                            gy1 = max(0, int(xyxy[1]) + tile.y_offset)
                            gx2 = min(w_frame, int(xyxy[2]) + tile.x_offset)
                            gy2 = min(h_frame, int(xyxy[3]) + tile.y_offset)
                            tile_boxes.append((gx1, gy1, gx2, gy2))
                            tile_scores.append(conf_val)

                # Apply NMS across tile boundaries
                keep_indices = TilerInferenceNMS = TiledInferenceEngine.apply_nms(
                    tile_boxes, tile_scores, iou_threshold=self.tiler.iou_threshold
                )
                for idx in keep_indices:
                    raw_candidates.append((tile_boxes[idx], tile_scores[idx], None))

            # 2. Standard Global Frame Inference (with or without ByteTrack)
            else:
                if self.use_tracking:
                    results = self.model.track(
                        source=frame,
                        persist=True,
                        classes=[0],
                        conf=feed_conf,
                        device=self.device,
                        tracker=self.tracker_type,
                        imgsz=self.imgsz,
                        rect=self.rect,
                        verbose=False,
                    )
                else:
                    results = self.model.predict(
                        source=frame,
                        classes=[0],
                        conf=feed_conf,
                        device=self.device,
                        imgsz=self.imgsz,
                        rect=self.rect,
                        verbose=False,
                    )

                if results and len(results) > 0 and results[0].boxes is not None:
                    boxes = results[0].boxes
                    for i in range(len(boxes)):
                        cls_id = int(boxes.cls[i].item()) if boxes.cls is not None else 0
                        if cls_id != 0:
                            continue

                        conf_val = float(boxes.conf[i].item()) if boxes.conf is not None else 0.0
                        xyxy = boxes.xyxy[i].cpu().numpy().astype(int)
                        bx1, by1, bx2, by2 = int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])

                        track_id = None
                        if boxes.id is not None:
                            try:
                                track_id = int(boxes.id[i].item())
                            except Exception:
                                track_id = None

                        raw_candidates.append(((bx1, by1, bx2, by2), conf_val, track_id))

        except Exception as e:
            logger.error(f"Inference error during person detection: {e}", exc_info=False)
            return []

        # 3. Candidate Evaluation & Audit Logging
        detections: List[Detection] = []
        rejected: List[RejectedDetection] = []
        current_frame_track_ids: List[int] = []

        for bbox, conf, tid in raw_candidates:
            bx1, by1, bx2, by2 = bbox
            box_h = max(1, by2 - by1)
            box_w = max(1, bx2 - bx1)
            box_h_ratio = box_h / float(max(1, h_frame))

            # Distance-adaptive threshold:
            # Distant persons (height < 30% of frame or < 150px) have fewer pixels; confidence scales down safely
            if box_h_ratio < 0.30 or box_h < 150:
                effective_threshold = max(0.18, self.confidence_threshold * 0.65)
            else:
                effective_threshold = self.confidence_threshold

            # Gate A: Confidence Threshold
            if conf < effective_threshold:
                rejected.append(
                    RejectedDetection(
                        bbox=bbox,
                        confidence=conf,
                        height_px=box_h,
                        width_px=box_w,
                        reason="CONFIDENCE_BELOW_THRESHOLD",
                        effective_threshold=effective_threshold,
                    )
                )
                logger.debug(
                    f"Candidate rejected: Confidence {conf:.3f} below effective threshold {effective_threshold:.3f} "
                    f"(bbox: {box_w}x{box_h}px)"
                )
                continue

            # Gate B: Minimum Bounding Box Size (reject sensor noise / high-frequency texture specks)
            if box_h < self.min_box_height_px or box_w < self.min_box_width_px:
                rejected.append(
                    RejectedDetection(
                        bbox=bbox,
                        confidence=conf,
                        height_px=box_h,
                        width_px=box_w,
                        reason="BELOW_MIN_BOX_SIZE",
                        effective_threshold=effective_threshold,
                    )
                )
                logger.debug(
                    f"Candidate rejected: Bounding box {box_w}x{box_h}px below minimum required "
                    f"{self.min_box_width_px}x{self.min_box_height_px}px (conf: {conf:.3f})"
                )
                continue

            # Accepted Detection
            det = Detection(
                class_name="person",
                confidence=conf,
                bbox=bbox,
                track_id=tid,
                timestamp=ts,
            )
            detections.append(det)
            if tid is not None:
                current_frame_track_ids.append(tid)

        # 4. Track Continuity and Loss Diagnostics
        active_set = set(current_frame_track_ids)
        lost_tracks = list(self._known_track_ids - active_set)
        self._known_track_ids.update(active_set)

        t_end = time.time()
        elapsed_ms = (t_end - t0) * 1000.0
        fps = 1.0 / max(0.001, (t_end - t0))

        # Record Diagnostics
        self.last_diagnostics = DetectionDiagnostics(
            inference_size=self.imgsz,
            inference_fps=round(fps, 1),
            inference_time_ms=round(elapsed_ms, 2),
            total_candidates=len(raw_candidates),
            accepted_count=len(detections),
            rejected_count=len(rejected),
            rejected_detections=rejected,
            active_track_ids=current_frame_track_ids,
            lost_track_ids=lost_tracks,
            tiled_inference_used=tiled_used,
        )

        return detections

    def get_diagnostics(self) -> Optional[DetectionDiagnostics]:
        """Returns the latest inference diagnostics metrics."""
        return self.last_diagnostics

    @staticmethod
    def draw_detections(
        frame: np.ndarray,
        detections: List[Detection],
        color: Tuple[int, int, int] = (0, 255, 0),
        show_metrics: bool = True,
    ) -> np.ndarray:
        """Draws bounding boxes, labels, height in pixels, and bottom-center anchor points."""
        annotated = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            id_str = f"ID:{det.track_id} " if det.track_id is not None else ""
            metrics_str = f" | H:{det.height_px}px" if show_metrics else ""
            label = f"{id_str}{det.class_name} {det.confidence:.2f}{metrics_str}"

            (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(
                annotated,
                (x1, max(0, y1 - th - baseline - 4)),
                (x1 + tw + 4, max(th + 4, y1)),
                color,
                -1,
            )
            cv2.putText(
                annotated,
                label,
                (x1 + 2, max(th, y1 - 2)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 0, 0),
                1,
                cv2.LINE_AA,
            )

            # Draw contact point
            cx, cy = det.bottom_center
            cv2.circle(annotated, (int(cx), int(cy)), 4, (0, 0, 255), -1)

        return annotated
