"""
Constant-Velocity Kalman Filter for FSOC beacon tracking.

State vector:
  x = [px, py, vx, vy]ᵀ

Transition model (constant velocity):
  px(k) = px(k-1) + vx(k-1)*dt
  py(k) = py(k-1) + vy(k-1)*dt
  vx(k) = vx(k-1)
  vy(k) = vy(k-1)

Measurement:
  z = [px, py]ᵀ

Equations:
  Predict:
    x̂⁻ = F x̂
    P⁻  = F P Fᵀ + Q

  Update (when measurement available):
    y   = z - H x̂⁻           (innovation)
    S   = H P⁻ Hᵀ + R        (innovation covariance)
    K   = P⁻ Hᵀ S⁻¹          (Kalman gain)
    x̂   = x̂⁻ + K y
    P   = (I - K H) P⁻       (Joseph form for numerical stability)
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class KalmanTracker:
    """
    Constant-velocity Kalman filter.

    Usage:
        tracker = KalmanTracker(process_noise=1.0, measurement_noise=5.0)
        tracker.initialize(x=320, y=240)
        pred_x, pred_y = tracker.predict(dt=0.033)
        tracker.update(measured_x=321, measured_y=241)
        state = tracker.get_state()
    """

    # State indices
    IDX_PX, IDX_PY, IDX_VX, IDX_VY = 0, 1, 2, 3

    def __init__(
        self,
        process_noise: float = 1.0,
        measurement_noise: float = 5.0,
        initial_covariance: float = 100.0,
        dt: float = 1.0 / 30.0,
    ) -> None:
        self._q  = process_noise
        self._r  = measurement_noise
        self._p0 = initial_covariance
        self._default_dt = dt

        # State and covariance
        self._x: np.ndarray = np.zeros(4, dtype=np.float64)
        self._P: np.ndarray = np.eye(4, dtype=np.float64) * initial_covariance

        # Measurement matrix H: extracts [px, py]
        self._H = np.array([[1, 0, 0, 0],
                             [0, 1, 0, 0]], dtype=np.float64)

        # Measurement noise covariance
        self._R = np.eye(2, dtype=np.float64) * measurement_noise

        self._initialized = False
        self._innovation  = np.zeros(2, dtype=np.float64)
        self._confidence  = 0.0

    # ------------------------------------------------------------------ #
    # Public interface
    # ------------------------------------------------------------------ #

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def position(self) -> Tuple[float, float]:
        return float(self._x[self.IDX_PX]), float(self._x[self.IDX_PY])

    @property
    def velocity(self) -> Tuple[float, float]:
        return float(self._x[self.IDX_VX]), float(self._x[self.IDX_VY])

    @property
    def confidence(self) -> float:
        return self._confidence

    @property
    def innovation(self) -> Tuple[float, float]:
        return float(self._innovation[0]), float(self._innovation[1])

    def initialize(self, x: float, y: float, vx: float = 0.0, vy: float = 0.0) -> None:
        """Initialize filter at given position with optional velocity estimate."""
        self._x = np.array([x, y, vx, vy], dtype=np.float64)
        self._P = np.eye(4, dtype=np.float64) * self._p0
        self._initialized = True
        self._confidence  = 0.5
        logger.debug("Kalman initialized at (%.1f, %.1f)", x, y)

    def reset(self) -> None:
        """Reset filter to uninitialized state."""
        self._x = np.zeros(4, dtype=np.float64)
        self._P = np.eye(4, dtype=np.float64) * self._p0
        self._initialized = False
        self._confidence  = 0.0
        self._innovation  = np.zeros(2, dtype=np.float64)

    def peek_predict(self, dt: Optional[float] = None) -> Tuple[float, float]:
        """
        Calculates projected (px, py) without mutating filter state.
        Useful for spatial gating prior to the official state machine update.
        """
        if not self._initialized:
            return float(self._x[self.IDX_PX]), float(self._x[self.IDX_PY])
        dt = dt if dt is not None else self._default_dt
        return (
            float(self._x[self.IDX_PX] + self._x[self.IDX_VX] * dt),
            float(self._x[self.IDX_PY] + self._x[self.IDX_VY] * dt),
        )

    def predict(self, dt: Optional[float] = None) -> Tuple[float, float]:
        """
        Run prediction step. Returns predicted (px, py).
        dt: timestep in seconds. Uses default_dt if None.
        """
        if not self._initialized:
            raise RuntimeError("KalmanTracker must be initialized before predict()")

        dt = dt if dt is not None else self._default_dt

        # State transition matrix for constant velocity
        F = np.array([
            [1, 0, dt, 0],
            [0, 1,  0, dt],
            [0, 0,  1, 0],
            [0, 0,  0, 1],
        ], dtype=np.float64)

        # Process noise covariance Q (continuous white noise acceleration model)
        dt2 = dt * dt
        dt3 = dt2 * dt
        dt4 = dt3 * dt
        q   = self._q

        Q = q * np.array([
            [dt4/4, 0,     dt3/2, 0    ],
            [0,     dt4/4, 0,     dt3/2],
            [dt3/2, 0,     dt2,   0    ],
            [0,     dt3/2, 0,     dt2  ],
        ], dtype=np.float64)

        # Predict
        self._x = F @ self._x
        self._P = F @ self._P @ F.T + Q

        # Confidence decreases during prediction
        self._confidence = max(self._confidence * 0.95, 0.1)

        return float(self._x[self.IDX_PX]), float(self._x[self.IDX_PY])

    def update(self, measured_x: float, measured_y: float) -> None:
        """
        Run update step with a new measurement.
        Should be called after predict().
        """
        if not self._initialized:
            self.initialize(measured_x, measured_y)
            return

        z = np.array([measured_x, measured_y], dtype=np.float64)

        # Innovation
        y = z - self._H @ self._x
        self._innovation = y

        # Innovation covariance
        S = self._H @ self._P @ self._H.T + self._R

        # Kalman gain
        K = self._P @ self._H.T @ np.linalg.inv(S)

        # Update state
        self._x = self._x + K @ y

        # Update covariance (Joseph form for numerical stability)
        I_KH = np.eye(4) - K @ self._H
        self._P = I_KH @ self._P @ I_KH.T + K @ self._R @ K.T

        # Confidence based on innovation magnitude
        innovation_norm = float(np.linalg.norm(y))
        self._confidence = float(np.clip(1.0 - innovation_norm / 100.0, 0.1, 1.0))

    def get_state(self) -> dict:
        """Return full state dict for telemetry/debug."""
        return {
            "px": float(self._x[0]),
            "py": float(self._x[1]),
            "vx": float(self._x[2]),
            "vy": float(self._x[3]),
            "confidence": self._confidence,
            "innovation_x": float(self._innovation[0]),
            "innovation_y": float(self._innovation[1]),
            "P_diag": [float(self._P[i, i]) for i in range(4)],
        }
