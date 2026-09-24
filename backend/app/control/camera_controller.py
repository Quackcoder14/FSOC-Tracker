"""
Camera Controller for FSOC terminal coarse pointing and tracking.

Coordinates tracking errors, dual-axis PID computation, and camera velocity actuation.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple, Dict, Any

from app.core.models import ControlResult
from app.control.error import TrackingErrorCalculator
from app.control.pid import DualAxisPID
from app.simulation.camera import VirtualCamera

logger = logging.getLogger(__name__)


class CameraController:
    """
    Closed-loop camera pointing controller.
    """

    def __init__(self, cfg: dict) -> None:
        cam_cfg = cfg.get("camera", {})
        res = cam_cfg.get("resolution", {})
        width = int(res.get("width", 640))
        height = int(res.get("height", 480))
        hfov = float(cam_cfg.get("hfov_deg", 4.0))
        vfov = float(cam_cfg.get("vfov_deg", 3.0))
        max_pan = float(cam_cfg.get("max_pan_speed_deg_s", 5.0))
        max_tilt = float(cam_cfg.get("max_tilt_speed_deg_s", 5.0))

        pid_cfg = cfg.get("pid", {})
        pan_pid = pid_cfg.get("pan", {})
        tilt_pid = pid_cfg.get("tilt", {})

        self.error_calculator = TrackingErrorCalculator(
            width=width,
            height=height,
            hfov_deg=hfov,
            vfov_deg=vfov,
        )

        self.pid = DualAxisPID(
            pan_cfg=pan_pid,
            tilt_cfg=tilt_pid,
            max_pan_speed=max_pan,
            max_tilt_speed=max_tilt,
        )

    def reset(self) -> None:
        """Reset PID states."""
        self.pid.reset()

    def update(
        self,
        target_x: Optional[float],
        target_y: Optional[float],
        dt: float,
        camera: Optional[VirtualCamera] = None,
    ) -> ControlResult:
        """
        Calculates control error, runs PID, and updates camera if provided.

        Args:
            target_x: Estimated target pixel x (from Kalman or detector)
            target_y: Estimated target pixel y
            dt: Time step in seconds
            camera: Optional VirtualCamera instance to actuate directly

        Returns:
            ControlResult containing pixel and angular errors and commands
        """
        if target_x is not None and target_y is not None:
            err_x_px, err_y_px, err_x_deg, err_y_deg = self.error_calculator.compute(
                target_x, target_y
            )
            pan_cmd, tilt_cmd = self.pid.update(err_x_deg, err_y_deg, dt)
        else:
            # Target not acquired: decay/zero commands
            err_x_px, err_y_px = 0.0, 0.0
            err_x_deg, err_y_deg = 0.0, 0.0
            pan_cmd, tilt_cmd = 0.0, 0.0
            # Note: keep PID integral from winding up while blind
            self.pid.reset()

        # Actuate physical or simulated camera
        if camera is not None:
            camera.update_pan_tilt(dt=dt, pan_cmd_deg_s=pan_cmd, tilt_cmd_deg_s=tilt_cmd)

        return ControlResult(
            error_x_px=err_x_px,
            error_y_px=err_y_px,
            error_x_deg=err_x_deg,
            error_y_deg=err_y_deg,
            pan_command_deg_s=pan_cmd,
            tilt_command_deg_s=tilt_cmd,
        )

    def get_diagnostics(self) -> Dict[str, Any]:
        return self.pid.get_telemetry()
