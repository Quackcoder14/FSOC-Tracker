"""
Virtual Camera for FSOC simulation.

Coordinate conventions:
  World frame:
    origin = scene center
    +x = right, +y = up
    units = degrees (relative to camera optical axis)

  Camera frame:
    pan  = rotation around vertical axis (positive = camera rotates right → target moves left)
    tilt = rotation around horizontal axis (positive = camera rotates up → target moves down)

  Image frame:
    origin = top-left
    +x = right, +y = down (OpenCV convention)
    (0, 0) is top-left pixel; (width-1, height-1) is bottom-right.

  Projection:
    Given camera pan/tilt (pan_deg, tilt_deg) and target world position
    (target_pan_deg, target_tilt_deg):

      angular_offset_x = target_pan_deg  - camera_pan_deg
      angular_offset_y = target_tilt_deg - camera_tilt_deg

    Pixel position (image coords):
      px = cx + angular_offset_x * (width  / hfov_deg)
      py = cy - angular_offset_y * (height / vfov_deg)   ← note sign: image-y is flipped

    where cx = width/2, cy = height/2.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CameraState:
    pan_deg: float  = 0.0   # Current camera pan (positive = camera pointing right)
    tilt_deg: float = 0.0   # Current camera tilt (positive = camera pointing up)


class VirtualCamera:
    """
    Geometric virtual camera model.

    Usage:
        camera = VirtualCamera(width=640, height=480, hfov_deg=4.0, vfov_deg=3.0)
        camera.reset()
        camera.update_pan_tilt(dt=0.033, pan_cmd=1.0, tilt_cmd=-0.5)
        px, py = camera.world_to_pixel(target_pan_deg=1.5, target_tilt_deg=0.2)
        frame = camera.render_scene(targets, ...)
    """

    def __init__(
        self,
        width: int,
        height: int,
        hfov_deg: float,
        vfov_deg: float,
        max_pan_speed_deg_s: float = 5.0,
        max_tilt_speed_deg_s: float = 5.0,
        update_rate_hz: float = 30.0,
    ) -> None:
        self.width  = width
        self.height = height
        self.hfov   = hfov_deg
        self.vfov   = vfov_deg
        self.max_pan_speed  = max_pan_speed_deg_s
        self.max_tilt_speed = max_tilt_speed_deg_s
        self.update_rate    = update_rate_hz

        # Derived pixel-per-degree scaling
        self._px_per_deg_x = width  / hfov_deg
        self._px_per_deg_y = height / vfov_deg

        self.state = CameraState()

    def reset(self) -> None:
        self.state = CameraState()

    # ------------------------------------------------------------------ #
    # Projection
    # ------------------------------------------------------------------ #

    def world_to_pixel(
        self, target_pan_deg: float, target_tilt_deg: float
    ) -> Tuple[float, float]:
        """
        Convert world target angular position to pixel coordinates.
        Returns (px, py) in image coords; may be outside [0, W) × [0, H).
        """
        # Angular offsets from camera boresight
        dx = target_pan_deg  - self.state.pan_deg
        dy = target_tilt_deg - self.state.tilt_deg

        cx = self.width  / 2.0
        cy = self.height / 2.0

        px = cx + dx * self._px_per_deg_x
        py = cy - dy * self._px_per_deg_y  # image-y increases downward

        return px, py

    def pixel_to_world(self, px: float, py: float) -> Tuple[float, float]:
        """Inverse of world_to_pixel."""
        cx = self.width  / 2.0
        cy = self.height / 2.0

        dx = (px - cx) / self._px_per_deg_x
        dy = (cy - py) / self._px_per_deg_y

        target_pan  = self.state.pan_deg  + dx
        target_tilt = self.state.tilt_deg + dy
        return target_pan, target_tilt

    def is_in_fov(self, target_pan_deg: float, target_tilt_deg: float) -> bool:
        """Return True if the target is within the camera FOV."""
        px, py = self.world_to_pixel(target_pan_deg, target_tilt_deg)
        return (0 <= px < self.width) and (0 <= py < self.height)

    # ------------------------------------------------------------------ #
    # Control update
    # ------------------------------------------------------------------ #

    def update_pan_tilt(
        self, dt: float, pan_cmd_deg_s: float, tilt_cmd_deg_s: float
    ) -> None:
        """
        Integrate angular velocity commands to update camera orientation.
        Commands are clamped to max speed limits.
        """
        pan_cmd  = float(np.clip(pan_cmd_deg_s,  -self.max_pan_speed,  self.max_pan_speed))
        tilt_cmd = float(np.clip(tilt_cmd_deg_s, -self.max_tilt_speed, self.max_tilt_speed))

        self.state.pan_deg  += pan_cmd  * dt
        self.state.tilt_deg += tilt_cmd * dt

    def update_fov(self, hfov_deg: float, vfov_deg: float) -> None:
        """
        Update the camera field-of-view at runtime and recalculate pixel/degree scaling.
        This affects world_to_pixel() projection for all subsequent frames.
        """
        if hfov_deg <= 0 or vfov_deg <= 0:
            raise ValueError(f"FOV must be positive, got hfov={hfov_deg}, vfov={vfov_deg}")
        self.hfov = float(hfov_deg)
        self.vfov = float(vfov_deg)
        self._px_per_deg_x = self.width  / self.hfov
        self._px_per_deg_y = self.height / self.vfov
        logger.info("VirtualCamera FOV updated: hfov=%.2f° vfov=%.2f° → %.1f px/° × %.1f px/°",
                    self.hfov, self.vfov, self._px_per_deg_x, self._px_per_deg_y)

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #

    def render_scene(
        self,
        targets: list[dict],  # list of {"pan_deg", "tilt_deg", "size_px", "brightness"}
        background_brightness: int = 20,
    ) -> np.ndarray:
        """
        Render the virtual scene as seen by this camera.
        Returns a BGR uint8 image of shape (H, W, 3).
        """
        # Dark background — space-like environment
        frame = np.full((self.height, self.width, 3), background_brightness, dtype=np.uint8)

        # Add some stars (static, seeded for reproducibility)
        rng = np.random.default_rng(12345)
        star_xs = rng.integers(0, self.width,  size=150)
        star_ys = rng.integers(0, self.height, size=150)
        star_br = rng.integers(40, 120, size=150)
        for sx, sy, sb in zip(star_xs, star_ys, star_br):
            frame[sy, sx] = [sb, sb, sb]

        # Render each target beacon
        for t in targets:
            px, py = self.world_to_pixel(t["pan_deg"], t["tilt_deg"])
            px_i, py_i = int(round(px)), int(round(py))
            size  = int(t.get("size_px", 10))
            brightness = int(t.get("brightness", 220))

            if -size <= px_i < self.width + size and -size <= py_i < self.height + size:
                # Draw Gaussian-profile beacon (more realistic than solid circle)
                for dy in range(-size * 2, size * 2 + 1):
                    for dx in range(-size * 2, size * 2 + 1):
                        ix, iy = px_i + dx, py_i + dy
                        if 0 <= ix < self.width and 0 <= iy < self.height:
                            dist_sq = dx * dx + dy * dy
                            sigma   = size / 2.0
                            val = brightness * np.exp(-dist_sq / (2 * sigma * sigma))
                            val = int(np.clip(val, 0, 255))
                            frame[iy, ix] = np.clip(
                                frame[iy, ix].astype(np.int32) + np.array([val, val, int(val * 0.9)]),
                                0, 255
                            ).astype(np.uint8)

        return frame

    def get_degrees_per_pixel(self) -> Tuple[float, float]:
        """Returns (deg/px_x, deg/px_y) for error conversion."""
        return (self.hfov / self.width, self.vfov / self.height)
