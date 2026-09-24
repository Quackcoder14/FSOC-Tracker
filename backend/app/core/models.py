"""
Core data models for the FSOC Virtual Camera Tracking System.

Coordinate conventions:
  - Image: origin top-left, x right, y down (OpenCV convention).
  - World: origin at scene center, x right, y up (standard math convention).
  - Angular: pan positive = camera moves right, tilt positive = camera moves up.
  - Error: error_x = target_x - image_center_x (positive = target is right of center).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import numpy as np


# ---------------------------------------------------------------------------
# Frame
# ---------------------------------------------------------------------------

@dataclass
class Frame:
    """A single captured or rendered frame with metadata."""
    image: np.ndarray          # HxWxC or HxW BGR/gray image
    frame_index: int           # Zero-based absolute frame number
    timestamp_ms: float        # Milliseconds from run start
    width: int
    height: int
    fps: float


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    """A single beacon candidate identified by classical CV."""
    x: float                   # Centroid x (image coords)
    y: float                   # Centroid y (image coords)
    area: float                # Bounding-box area in px²
    brightness: float          # Mean pixel intensity [0,255]
    shape_score: float         # Compactness/circularity score [0,1]
    proximity_score: float     # Distance-based score from Kalman prediction [0,1]
    cv_score: float            # Composite classical CV score [0,1]
    ai_score: Optional[float]  # CNN beacon probability [0,1] or None
    final_score: float         # Combined final score [0,1]


@dataclass
class DetectionResult:
    """Output of one detection pass over a frame."""
    detected: bool
    x: Optional[float]
    y: Optional[float]
    confidence: float
    candidate_count: int
    candidates: list[Candidate] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tracking
# ---------------------------------------------------------------------------

class TrackingState(Enum):
    SEARCH = "SEARCH"
    ACQUIRE = "ACQUIRE"
    TRACK = "TRACK"
    PREDICT = "PREDICT"
    REACQUIRE = "REACQUIRE"
    LOST = "LOST"


@dataclass
class TrackingResult:
    """Output of one Kalman tracker update."""
    predicted_x: float
    predicted_y: float
    measured_x: Optional[float]
    measured_y: Optional[float]
    velocity_x: float
    velocity_y: float
    confidence: float
    state: TrackingState
    innovation_x: float = 0.0  # Measurement residual x
    innovation_y: float = 0.0  # Measurement residual y


# ---------------------------------------------------------------------------
# Control
# ---------------------------------------------------------------------------

@dataclass
class ControlResult:
    """Output of the PID camera controller for one frame."""
    error_x_px: float
    error_y_px: float
    error_x_deg: float
    error_y_deg: float
    pan_command_deg_s: float   # Angular velocity command for pan axis
    tilt_command_deg_s: float  # Angular velocity command for tilt axis


# ---------------------------------------------------------------------------
# Disturbances
# ---------------------------------------------------------------------------

@dataclass
class DisturbanceState:
    """Current state of the disturbance engine."""
    enabled: bool

    gaussian_enabled: bool
    gaussian_sigma: float

    salt_pepper_enabled: bool
    salt_pepper_probability: float

    poisson_enabled: bool

    atmosphere_type: str  # "clear", "haze", "fog", "rain"

    low_light_enabled: bool
    blur_enabled: bool
    blur_kernel_size: int = 3

    camera_jitter_x: float = 0.0
    camera_jitter_y: float = 0.0

    platform_motion_x: float = 0.0
    platform_motion_y: float = 0.0


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@dataclass
class MetricsResult:
    """Accumulated performance metrics for a run."""
    instantaneous_error_px: Optional[float]
    rmse_px: Optional[float]
    mean_error_px: Optional[float]
    max_error_px: Optional[float]
    median_error_px: Optional[float]

    acquisition_time_ms: Optional[float]
    reacquisition_time_ms: Optional[float]

    # Fraction of frames where state == TRACK (not PREDICT/SEARCH/etc.)
    lock_retention_percent: float

    processing_fps: float
    processing_time_ms: float
    max_processing_time_ms: float

    frames_processed: int
    frames_lost: int           # Frames where detection == False
    target_loss_count: int     # Number of distinct tracking-loss events


# ---------------------------------------------------------------------------
# World State (for 3D visualization)
# ---------------------------------------------------------------------------

@dataclass
class WorldState:
    """World geometry state for 3D visualization."""
    # Target position in world coordinates (meters)
    target_position: Tuple[float, float, float] = (0.0, 0.0, 10.0)
    # Camera position in world coordinates (meters)
    camera_position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    # Camera orientation
    camera_pan_deg: float = 0.0
    camera_tilt_deg: float = 0.0
    # Boresight direction vector (normalized)
    boresight_direction: Tuple[float, float, float] = (0.0, 0.0, 1.0)
    # Field of view
    hfov_deg: float = 4.0
    vfov_deg: float = 3.0
    # Distance to target (meters)
    target_distance: float = 10.0


# ---------------------------------------------------------------------------
# Telemetry (wire format helpers)
# ---------------------------------------------------------------------------

@dataclass
class TelemetryPacket:
    """
    Complete telemetry snapshot sent from Python sidecar to frontend.
    Serialised to MessagePack on the wire.
    """
    frame_index: int
    timestamp_ms: float

    detection: Optional[dict] = None
    tracking: Optional[dict] = None
    control: Optional[dict] = None
    performance: Optional[dict] = None
    disturbance: Optional[dict] = None
    ground_truth: Optional[dict] = None  # Only in simulation mode
    world: Optional[dict] = None  # World state for 3D visualization
    mode: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "type": "FRAME_UPDATE",
            "frame_index": self.frame_index,
            "timestamp_ms": self.timestamp_ms,
            "mode": self.mode,
            "detection": self.detection,
            "tracking": self.tracking,
            "control": self.control,
            "performance": self.performance,
            "disturbance": self.disturbance,
            "ground_truth": self.ground_truth,
            "world": self.world,
        }
