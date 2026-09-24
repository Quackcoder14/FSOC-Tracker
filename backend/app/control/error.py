"""
Tracking error calculator for FSOC beam alignment.

Converts pixel displacements from the image center into angular errors (degrees),
matching the camera model coordinate conventions:
  - cx = width / 2, cy = height / 2
  - error_x_px = px - cx  (positive = target is right of center)
  - error_y_px = py - cy  (positive = target is below center)
  - error_x_deg = error_x_px * (hfov_deg / width)
  - error_y_deg = -error_y_px * (vfov_deg / height)  (positive = target is above center)
"""

from __future__ import annotations

from typing import Tuple


class TrackingErrorCalculator:
    """
    Computes pixel and angular tracking errors relative to camera boresight.
    """

    def __init__(
        self,
        width: int,
        height: int,
        hfov_deg: float,
        vfov_deg: float,
    ) -> None:
        self.width = width
        self.height = height
        self.hfov_deg = hfov_deg
        self.vfov_deg = vfov_deg

        self.cx = width / 2.0
        self.cy = height / 2.0

        self.deg_per_px_x = hfov_deg / float(width)
        self.deg_per_px_y = vfov_deg / float(height)

    def compute(
        self, target_px: float, target_py: float
    ) -> Tuple[float, float, float, float]:
        """
        Calculates error for a given pixel coordinate.

        Returns:
            (error_x_px, error_y_px, error_x_deg, error_y_deg)
        """
        error_x_px = target_px - self.cx
        error_y_px = target_py - self.cy

        error_x_deg = error_x_px * self.deg_per_px_x
        # Inverted image y-axis: target above center has py < cy, so positive tilt error
        error_y_deg = -error_y_px * self.deg_per_px_y

        return error_x_px, error_y_px, error_x_deg, error_y_deg
