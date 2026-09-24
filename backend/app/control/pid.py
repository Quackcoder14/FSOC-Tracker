"""
PID controller with anti-windup and derivative filtering for FSOC terminal tracking.
"""

from __future__ import annotations

from typing import Optional, Tuple, Dict, Any
import numpy as np


class PIDController:
    """
    Single-axis PID controller with anti-windup and saturation limits.
    """

    def __init__(
        self,
        kp: float = 0.8,
        ki: float = 0.02,
        kd: float = 0.10,
        output_limits: Tuple[float, float] = (-5.0, 5.0),
        integral_limits: Optional[Tuple[float, float]] = None,
    ) -> None:
        self.kp = float(kp)
        self.ki = float(ki)
        self.kd = float(kd)
        self.min_out, self.max_out = output_limits

        if integral_limits is not None:
            self.min_int, self.max_int = integral_limits
        else:
            # Default integral limit to prevent windup beyond max output range
            span = abs(self.max_out - self.min_out)
            self.min_int = -span
            self.max_int = span

        self._integral: float = 0.0
        self._prev_error: Optional[float] = None
        self._last_p: float = 0.0
        self._last_i: float = 0.0
        self._last_d: float = 0.0
        self._last_output: float = 0.0

    def reset(self) -> None:
        """Reset internal integrator and memory."""
        self._integral = 0.0
        self._prev_error = None
        self._last_p = 0.0
        self._last_i = 0.0
        self._last_d = 0.0
        self._last_output = 0.0

    def update(self, error: float, dt: float) -> float:
        """
        Compute control output for current error.

        Args:
            error: Current error signal (e.g. error in degrees)
            dt: Elapsed time in seconds since previous update
        """
        if dt <= 0.0:
            return self._last_output

        # Proportional term
        p_term = self.kp * error

        # Integral term with anti-windup clamping
        self._integral += error * dt
        self._integral = float(np.clip(self._integral, self.min_int, self.max_int))
        i_term = self.ki * self._integral

        # Derivative term
        if self._prev_error is not None:
            derivative = (error - self._prev_error) / dt
        else:
            derivative = 0.0
        d_term = self.kd * derivative

        self._prev_error = error

        raw_output = p_term + i_term + d_term
        output = float(np.clip(raw_output, self.min_out, self.max_out))

        self._last_p = p_term
        self._last_i = i_term
        self._last_d = d_term
        self._last_output = output

        return output

    def get_telemetry(self) -> Dict[str, float]:
        """Return diagnostic metrics."""
        return {
            "p": self._last_p,
            "i": self._last_i,
            "d": self._last_d,
            "output": self._last_output,
            "integral": self._integral,
        }


class DualAxisPID:
    """
    Manages dual-axis (Pan and Tilt) PID control for coarse beam tracking.
    """

    def __init__(
        self,
        pan_cfg: dict,
        tilt_cfg: dict,
        max_pan_speed: float = 5.0,
        max_tilt_speed: float = 5.0,
    ) -> None:
        self.pan = PIDController(
            kp=float(pan_cfg.get("kp", 0.8)),
            ki=float(pan_cfg.get("ki", 0.02)),
            kd=float(pan_cfg.get("kd", 0.10)),
            output_limits=(-max_pan_speed, max_pan_speed),
        )
        self.tilt = PIDController(
            kp=float(tilt_cfg.get("kp", 0.8)),
            ki=float(tilt_cfg.get("ki", 0.02)),
            kd=float(tilt_cfg.get("kd", 0.10)),
            output_limits=(-max_tilt_speed, max_tilt_speed),
        )

    def reset(self) -> None:
        self.pan.reset()
        self.tilt.reset()

    def update(
        self, error_x_deg: float, error_y_deg: float, dt: float
    ) -> Tuple[float, float]:
        """
        Calculates pan and tilt commands (in deg/s).
        """
        pan_cmd = self.pan.update(error_x_deg, dt)
        tilt_cmd = self.tilt.update(error_y_deg, dt)
        return pan_cmd, tilt_cmd

    def get_telemetry(self) -> Dict[str, Any]:
        return {
            "pan": self.pan.get_telemetry(),
            "tilt": self.tilt.get_telemetry(),
        }
