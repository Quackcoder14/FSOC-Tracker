"""
VirtualCameraSource — integrates camera, target trajectory, and disturbance engine.
Implements FrameSource for use in the common tracking pipeline.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np

from app.core.interfaces import FrameSource
from app.core.models import Frame
from app.simulation.camera import VirtualCamera
from app.simulation.target import Trajectory, TargetState, create_trajectory
from app.simulation.disturbances import DisturbanceEngine

logger = logging.getLogger(__name__)


class VirtualCameraSource(FrameSource):
    """
    Generates synthetic frames for simulation mode.

    Simulation loop:
      t → trajectory.get_state(t) → render scene → apply disturbances → Frame
    """

    def __init__(self, cfg: dict) -> None:
        cam_cfg  = cfg.get("camera", {})
        res      = cam_cfg.get("resolution", {})

        self._width  = int(res.get("width",  640))
        self._height = int(res.get("height", 480))
        self._fps    = float(cfg.get("system", {}).get("target_fps", 30))

        self._camera = VirtualCamera(
            width=self._width,
            height=self._height,
            hfov_deg=float(cam_cfg.get("hfov_deg", 4.0)),
            vfov_deg=float(cam_cfg.get("vfov_deg", 3.0)),
            max_pan_speed_deg_s=float(cam_cfg.get("max_pan_speed_deg_s", 5.0)),
            max_tilt_speed_deg_s=float(cam_cfg.get("max_tilt_speed_deg_s", 5.0)),
        )

        beacon_cfg = cfg.get("beacon", {})
        self._beacon_size_px = int(beacon_cfg.get("size_px", 10))
        self._beacon_brightness = 220

        traj_cfg = cfg.get("trajectory", {})
        self._trajectory: Trajectory = create_trajectory(
            traj_cfg,
            size_px=self._beacon_size_px,
            brightness=self._beacon_brightness,
        )

        seed = int(cfg.get("system", {}).get("seed", 42))
        self._disturbance_engine = DisturbanceEngine(cfg, seed=seed)

        self._frame_index: int = 0
        self._running: bool = False
        self._start_time: float = 0.0

        # Expose camera and last target state for ground-truth access
        self.camera = self._camera
        self.last_target_state: Optional[TargetState] = None
        self.last_disturbance_context: Optional[dict] = None

    # ------------------------------------------------------------------ #
    # FrameSource interface
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        self._camera.reset()
        self._frame_index = 0
        self._running = True
        self._start_time = time.monotonic()
        logger.info("VirtualCameraSource started: %dx%d @ %.0f fps", 
                    self._width, self._height, self._fps)

    def read(self) -> Optional[Frame]:
        if not self._running:
            return None

        t = self._frame_index / self._fps
        ts_ms = t * 1000.0

        # Get true target state (ground truth — isolated, NOT passed to detector)
        target_state = self._trajectory.get_state(t)
        self.last_target_state = target_state

        # Render scene
        targets = [{
            "pan_deg":   target_state.pan_deg,
            "tilt_deg":  target_state.tilt_deg,
            "size_px":   target_state.size_px,
            "brightness": target_state.brightness,
        }]
        raw_image = self._camera.render_scene(targets)

        # Apply disturbances
        disturbed_image, dist_context = self._disturbance_engine.apply(
            raw_image, self._frame_index)
        self.last_disturbance_context = dist_context

        frame = Frame(
            image=disturbed_image,
            frame_index=self._frame_index,
            timestamp_ms=ts_ms,
            width=self._width,
            height=self._height,
            fps=self._fps,
        )
        self._frame_index += 1
        return frame

    def stop(self) -> None:
        self._running = False
        logger.info("VirtualCameraSource stopped after %d frames", self._frame_index)

    def get_fps(self) -> float:
        return self._fps

    def get_frame_count(self) -> Optional[int]:
        return None  # Infinite source

    def get_timestamp_ms(self) -> float:
        return (self._frame_index / self._fps) * 1000.0

    # ------------------------------------------------------------------ #
    # Control interface (called by camera controller)
    # ------------------------------------------------------------------ #

    def apply_control(self, pan_cmd_deg_s: float, tilt_cmd_deg_s: float) -> None:
        """Apply PID output to the virtual camera."""
        dt = 1.0 / self._fps
        self._camera.update_pan_tilt(dt, pan_cmd_deg_s, tilt_cmd_deg_s)

    def update_trajectory(self, traj_cfg: dict) -> None:
        """Update simulation target trajectory dynamically."""
        if "size_px" in traj_cfg:
            self._beacon_size_px = int(traj_cfg["size_px"])
        from app.simulation.target import TrajectoryType
        traj_type = TrajectoryType.from_string(traj_cfg.get("type", "circular"))
        self._trajectory = create_trajectory(
            traj_cfg,
            size_px=self._beacon_size_px,
            brightness=self._beacon_brightness,
        )
        self._frame_index = 0
        self._camera.reset()
        logger.info("Simulation trajectory updated: %s", traj_type.value)

    def update_disturbances(self, overrides: dict) -> None:
        """Runtime disturbance parameter update (from UI)."""
        self._disturbance_engine.update_from_dict(overrides)

    def update_camera(self, camera_settings: dict) -> None:
        """
        Update virtual camera parameters at runtime (called from engine).

        Supported keys:
          hfov_deg   — horizontal field of view in degrees
          vfov_deg   — vertical field of view in degrees (defaults to hfov * 3/4 if omitted)
          beacon_size_px — new beacon spot size
        """
        hfov = float(camera_settings.get("hfov_deg", self._camera.hfov))
        vfov = float(camera_settings.get("vfov_deg", hfov * (3.0 / 4.0)))
        self._camera.update_fov(hfov, vfov)
        if "beacon_size_px" in camera_settings:
            self._beacon_size_px = int(camera_settings["beacon_size_px"])
        logger.info("VirtualCameraSource camera updated: hfov=%.2f° vfov=%.2f°", hfov, vfov)

    def get_disturbance_state(self):
        return self._disturbance_engine.get_state()

    def get_disturbance_context(self) -> Optional[dict]:
        """Return the last disturbance context (includes jitter and platform motion)."""
        return self.last_disturbance_context

    def get_ground_truth(self) -> Optional[dict]:
        """Return true target pixel position (for metrics only — never fed to tracker)."""
        if self.last_target_state is None:
            return None
        px, py = self._camera.world_to_pixel(
            self.last_target_state.pan_deg,
            self.last_target_state.tilt_deg,
        )
        return {
            "pan_deg":   self.last_target_state.pan_deg,
            "tilt_deg":  self.last_target_state.tilt_deg,
            "pixel_x":   px,
            "pixel_y":   py,
        }
