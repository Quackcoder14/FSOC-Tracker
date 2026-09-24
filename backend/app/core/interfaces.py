"""
Abstract base classes (interfaces) for the FSOC tracking system.
The core engine must NOT depend on UI, WebSocket, or Tauri.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.core.models import Frame


class FrameSource(ABC):
    """
    Abstract source that provides frames to the tracking pipeline.
    Implementations: VirtualCameraSource, VideoFileSource, (WebcamSource).
    """

    @abstractmethod
    def start(self) -> None:
        """Open/initialise the source. Must be called before read()."""
        ...

    @abstractmethod
    def read(self) -> Optional[Frame]:
        """
        Return the next Frame, or None when the source is exhausted/closed.
        The returned Frame must have valid frame_index and timestamp_ms.
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """Release all resources. Safe to call multiple times."""
        ...

    @abstractmethod
    def get_fps(self) -> float:
        """Return the nominal FPS of this source."""
        ...

    def get_frame_count(self) -> Optional[int]:
        """
        Return total frame count if known (e.g. for a video file),
        or None for live/infinite sources.
        """
        return None

    def get_timestamp_ms(self) -> float:
        """
        Return the current source time in milliseconds.
        Default: derived from frame_index and fps.
        """
        return 0.0


class Disturbance(ABC):
    """Abstract disturbance module applied to frames by the DisturbanceEngine."""

    @abstractmethod
    def apply(self, frame: "import numpy as np; np.ndarray", context: dict) -> "import numpy as np; np.ndarray":
        """
        Apply disturbance to the image array.
        context: dict with keys such as 'frame_index', 'timestamp_ms', 'rng'.
        Must return the modified image (may be in-place).
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this disturbance."""
        ...
