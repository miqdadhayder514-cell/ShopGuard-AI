"""
ShopGuard AI - Tiled / Sliced Inference Engine
Optional high-resolution CCTV processing mode for detecting small, distant people.
Splits high-resolution video frames into overlapping tiles, executes YOLO detection,
translates coordinates back to global frame space, and applies Non-Maximum Suppression (NMS).
"""

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple
import cv2
import numpy as np

from ..utils.logger import get_logger

logger = get_logger("detection.tiled")


@dataclass
class TileSlice:
    """Represents a spatial slice of a larger video frame."""
    image: np.ndarray
    x_offset: int
    y_offset: int
    width: int
    height: int


class TiledInferenceEngine:
    """
    Splits high-resolution CCTV frames (e.g., 1080p, 1440p, 4K) into overlapping tiles,
    runs person detection per tile, and merges bounding boxes using Non-Maximum Suppression (NMS).
    Prevents small, distant people from vanishing due to aggressive full-frame downscaling.
    """

    def __init__(
        self,
        grid: Tuple[int, int] = (2, 2),
        overlap: float = 0.20,
        iou_threshold: float = 0.45,
    ):
        self.rows = max(1, int(grid[0]))
        self.cols = max(1, int(grid[1]))
        self.overlap = float(max(0.0, min(0.5, overlap)))
        self.iou_threshold = float(iou_threshold)

    def generate_tiles(self, frame: np.ndarray) -> List[TileSlice]:
        """
        Generates overlapping rectangular tiles from the input image.
        """
        if frame is None or frame.size == 0:
            return []

        h, w = frame.shape[:2]
        if self.rows == 1 and self.cols == 1:
            return [TileSlice(image=frame, x_offset=0, y_offset=0, width=w, height=h)]

        # Calculate base tile dimensions including overlap
        base_tile_w = int(w / (self.cols - (self.cols - 1) * self.overlap)) if self.cols > 1 else w
        base_tile_h = int(h / (self.rows - (self.rows - 1) * self.overlap)) if self.rows > 1 else h

        # Ensure valid positive dimensions
        tile_w = max(32, min(w, base_tile_w))
        tile_h = max(32, min(h, base_tile_h))

        step_x = int(tile_w * (1.0 - self.overlap)) if self.cols > 1 else w
        step_y = int(tile_h * (1.0 - self.overlap)) if self.rows > 1 else h

        tiles: List[TileSlice] = []

        for r in range(self.rows):
            y1 = r * step_y
            if r == self.rows - 1:
                y1 = max(0, h - tile_h)
            y2 = min(h, y1 + tile_h)

            for c in range(self.cols):
                x1 = c * step_x
                if c == self.cols - 1:
                    x1 = max(0, w - tile_w)
                x2 = min(w, x1 + tile_w)

                tile_crop = frame[y1:y2, x1:x2]
                tiles.append(
                    TileSlice(
                        image=tile_crop,
                        x_offset=x1,
                        y_offset=y1,
                        width=x2 - x1,
                        height=y2 - y1,
                    )
                )

        return tiles

    @staticmethod
    def apply_nms(
        boxes: List[Tuple[int, int, int, int]],
        scores: List[float],
        iou_threshold: float = 0.45,
    ) -> List[int]:
        """
        Executes Non-Maximum Suppression to remove overlapping redundant detections.
        Returns indices of kept boxes.
        """
        if not boxes:
            return []

        boxes_array = np.array(boxes, dtype=float)
        scores_array = np.array(scores, dtype=float)

        x1 = boxes_array[:, 0]
        y1 = boxes_array[:, 1]
        x2 = boxes_array[:, 2]
        y2 = boxes_array[:, 3]

        areas = (x2 - x1 + 1) * (y2 - y1 + 1)
        order = scores_array.argsort()[::-1]

        keep: List[int] = []

        while order.size > 0:
            i = order[0]
            keep.append(int(i))

            if order.size == 1:
                break

            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0.0, xx2 - xx1 + 1)
            h = np.maximum(0.0, yy2 - yy1 + 1)
            inter = w * h

            ovr = inter / (areas[i] + areas[order[1:]] - inter)

            inds = np.where(ovr <= iou_threshold)[0]
            order = order[inds + 1]

        return keep
