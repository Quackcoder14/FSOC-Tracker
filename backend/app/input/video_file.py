"""
VideoFileSource — wraps OpenCV VideoCapture for MP4/AVI input.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from app.core.interfaces import FrameSource
from app.core.models import Frame

logger = logging.getLogger(__name__)


class VideoFileSource(FrameSource):
    """
    Reads frames from an MP4 (or any OpenCV-supported) video file.

    Frame identity:
      frame_index = 0-based absolute frame counter
      timestamp_ms = frame_index / fps * 1000
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame_index: int = 0
        self._fps: float = 30.0
        self._frame_count: Optional[int] = None
        self._width: int = 0
        self._height: int = 0

    # ------------------------------------------------------------------ #
    # FrameSource interface
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        if not self._path.exists():
            raise FileNotFoundError(f"Video file not found: {self._path}")

        self._cap = cv2.VideoCapture(str(self._path))
        if not self._cap.isOpened():
            raise IOError(f"Cannot open video file: {self._path}")

        self._fps = float(self._cap.get(cv2.CAP_PROP_FPS)) or 30.0
        total = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._frame_count = total if total > 0 else None
        self._width  = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._frame_index = 0

        logger.info(
            "VideoFileSource started: %s | %.1f fps | %dx%d | %s frames",
            self._path.name,
            self._fps,
            self._width,
            self._height,
            self._frame_count or "unknown",
        )

    def read(self) -> Optional[Frame]:
        if self._cap is None or not self._cap.isOpened():
            return None

        ret, image = self._cap.read()
        if not ret:
            return None  # End of video

        ts_ms = self._frame_index / self._fps * 1000.0
        frame = Frame(
            image=image,
            frame_index=self._frame_index,
            timestamp_ms=ts_ms,
            width=self._width,
            height=self._height,
            fps=self._fps,
        )
        self._frame_index += 1
        return frame

    def stop(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("VideoFileSource stopped after %d frames", self._frame_index)

    def get_fps(self) -> float:
        return self._fps

    def get_frame_count(self) -> Optional[int]:
        return self._frame_count

    def get_timestamp_ms(self) -> float:
        return self._frame_index / self._fps * 1000.0

    # ------------------------------------------------------------------ #
    # Extra metadata
    # ------------------------------------------------------------------ #

    def get_metadata(self) -> dict:
        return {
            "path": str(self._path),
            "fps": self._fps,
            "frame_count": self._frame_count,
            "width": self._width,
            "height": self._height,
            "duration_s": (self._frame_count / self._fps) if self._frame_count else None,
        }
