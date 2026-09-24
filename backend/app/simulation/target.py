"""
Target trajectory generators for simulation.

All trajectories operate in world angular space (degrees).
pan_deg  = horizontal angular position (positive = right)
tilt_deg = vertical angular position   (positive = up)
"""

from __future__ import annotations

import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np


class TrajectoryType(Enum):
    """Canonical trajectory identifiers used throughout the backend."""
    LINEAR = "linear"
    CIRCULAR = "circular"
    FIGURE8 = "figure8"
    RANDOM = "random"
    ACCEPTANCE = "acceptance"

    @classmethod
    def from_string(cls, value: str) -> "TrajectoryType":
        """Parse string to TrajectoryType, accepting aliases."""
        v = value.lower().strip()
        aliases = {
            "straight": cls.LINEAR,
            "linear": cls.LINEAR,
            "circular": cls.CIRCULAR,
            "circle": cls.CIRCULAR,
            "figure8": cls.FIGURE8,
            "figure-8": cls.FIGURE8,
            "lissajous": cls.FIGURE8,
            "random": cls.RANDOM,
            "random_walk": cls.RANDOM,
            "acceptance": cls.ACCEPTANCE,
            "off_axis": cls.ACCEPTANCE,
            "off-axis": cls.ACCEPTANCE,
        }
        return aliases.get(v, cls.CIRCULAR)

    def to_trajectory_class(self):
        """Return the corresponding trajectory class."""
        mapping = {
            TrajectoryType.LINEAR: StraightLineTrajectory,
            TrajectoryType.CIRCULAR: CircularTrajectory,
            TrajectoryType.FIGURE8: Figure8Trajectory,
            TrajectoryType.RANDOM: RandomTrajectory,
            TrajectoryType.ACCEPTANCE: StraightLineTrajectory,  # Static off-axis
        }
        return mapping[self]


@dataclass
class TargetState:
    """Instantaneous state of a simulated target."""
    pan_deg:   float
    tilt_deg:  float
    vel_pan_deg_s:  float = 0.0
    vel_tilt_deg_s: float = 0.0
    size_px:    int   = 10
    brightness: int   = 220


class Trajectory(ABC):
    """Abstract base for all trajectory generators."""

    @abstractmethod
    def get_state(self, t: float) -> TargetState:
        """Return target state at time t (seconds from start)."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class StraightLineTrajectory(Trajectory):
    """Target moves in a straight line at constant angular velocity."""

    name = "straight"

    def __init__(
        self,
        start_pan_deg: float = -1.5,
        start_tilt_deg: float = 0.0,
        vel_pan_deg_s: float = 0.5,
        vel_tilt_deg_s: float = 0.1,
        size_px: int = 10,
        brightness: int = 220,
    ) -> None:
        self.start_pan   = start_pan_deg
        self.start_tilt  = start_tilt_deg
        self.vel_pan     = vel_pan_deg_s
        self.vel_tilt    = vel_tilt_deg_s
        self.size_px     = size_px
        self.brightness  = brightness

    def get_state(self, t: float) -> TargetState:
        return TargetState(
            pan_deg=self.start_pan  + self.vel_pan  * t,
            tilt_deg=self.start_tilt + self.vel_tilt * t,
            vel_pan_deg_s=self.vel_pan,
            vel_tilt_deg_s=self.vel_tilt,
            size_px=self.size_px,
            brightness=self.brightness,
        )


class CircularTrajectory(Trajectory):
    """Target orbits in a circle of angular radius (amplitude_x, amplitude_y)."""

    name = "circular"

    def __init__(
        self,
        center_pan_deg: float = 0.0,
        center_tilt_deg: float = 0.0,
        amplitude_x_deg: float = 1.0,
        amplitude_y_deg: float = 0.7,
        speed_deg_s: float = 1.5,
        size_px: int = 10,
        brightness: int = 220,
    ) -> None:
        self.cx    = center_pan_deg
        self.cy    = center_tilt_deg
        self.ax    = amplitude_x_deg
        self.ay    = amplitude_y_deg
        self.omega = speed_deg_s  # angular speed (rad/s equivalent)
        self.size_px    = size_px
        self.brightness = brightness

    def get_state(self, t: float) -> TargetState:
        # angular speed in rad/s such that one cycle = 2*pi*amplitude / speed_deg_s
        period = 2 * math.pi * max(self.ax, self.ay) / self.omega
        w = 2 * math.pi / period

        pan  = self.cx + self.ax * math.cos(w * t)
        tilt = self.cy + self.ay * math.sin(w * t)
        vpan  = -self.ax * w * math.sin(w * t)
        vtilt =  self.ay * w * math.cos(w * t)

        return TargetState(
            pan_deg=pan, tilt_deg=tilt,
            vel_pan_deg_s=vpan, vel_tilt_deg_s=vtilt,
            size_px=self.size_px, brightness=self.brightness,
        )


class Figure8Trajectory(Trajectory):
    """Figure-eight (Lissajous) trajectory."""

    name = "figure8"

    def __init__(
        self,
        center_pan_deg: float = 0.0,
        center_tilt_deg: float = 0.0,
        amplitude_x_deg: float = 1.2,
        amplitude_y_deg: float = 0.8,
        speed_deg_s: float = 2.0,
        size_px: int = 10,
        brightness: int = 220,
    ) -> None:
        self.cx = center_pan_deg
        self.cy = center_tilt_deg
        self.ax = amplitude_x_deg
        self.ay = amplitude_y_deg
        self.speed  = speed_deg_s
        self.size_px    = size_px
        self.brightness = brightness

    def get_state(self, t: float) -> TargetState:
        # x: frequency 1, y: frequency 2 → classic figure-8
        period = 2 * math.pi * max(self.ax, self.ay) / self.speed
        w = 2 * math.pi / period

        pan   = self.cx + self.ax * math.sin(w * t)
        tilt  = self.cy + self.ay * math.sin(2 * w * t)
        vpan  = self.ax * w * math.cos(w * t)
        vtilt = self.ay * 2 * w * math.cos(2 * w * t)

        return TargetState(
            pan_deg=pan, tilt_deg=tilt,
            vel_pan_deg_s=vpan, vel_tilt_deg_s=vtilt,
            size_px=self.size_px, brightness=self.brightness,
        )


class RandomTrajectory(Trajectory):
    """
    Random-walk trajectory: smooth random motion using sinusoidal sum.
    Uses a fixed random seed for reproducibility.
    """

    name = "random"

    def __init__(
        self,
        amplitude_x_deg: float = 1.5,
        amplitude_y_deg: float = 1.0,
        speed_deg_s: float = 2.0,
        seed: int = 42,
        size_px: int = 10,
        brightness: int = 220,
    ) -> None:
        self.ax = amplitude_x_deg
        self.ay = amplitude_y_deg
        self.speed  = speed_deg_s
        self.size_px    = size_px
        self.brightness = brightness

        # Pre-generate harmonics for smooth random motion
        rng = np.random.default_rng(seed)
        N = 8
        self._freqs_x  = rng.uniform(0.1, 1.2, N)
        self._phases_x = rng.uniform(0, 2 * math.pi, N)
        self._amps_x   = rng.dirichlet(np.ones(N))  # sums to 1

        self._freqs_y  = rng.uniform(0.1, 1.2, N)
        self._phases_y = rng.uniform(0, 2 * math.pi, N)
        self._amps_y   = rng.dirichlet(np.ones(N))

    def get_state(self, t: float) -> TargetState:
        pan  = self.ax * float(np.sum(self._amps_x * np.sin(
            2 * math.pi * self._freqs_x * t + self._phases_x)))
        tilt = self.ay * float(np.sum(self._amps_y * np.sin(
            2 * math.pi * self._freqs_y * t + self._phases_y)))

        vpan  = self.ax * float(np.sum(self._amps_x * 2 * math.pi * self._freqs_x *
                                        np.cos(2 * math.pi * self._freqs_x * t + self._phases_x)))
        vtilt = self.ay * float(np.sum(self._amps_y * 2 * math.pi * self._freqs_y *
                                        np.cos(2 * math.pi * self._freqs_y * t + self._phases_y)))

        return TargetState(
            pan_deg=pan, tilt_deg=tilt,
            vel_pan_deg_s=vpan, vel_tilt_deg_s=vtilt,
            size_px=self.size_px, brightness=self.brightness,
        )


def create_trajectory(cfg: dict, size_px: int = 10, brightness: int = 220) -> Trajectory:
    """Factory: create a Trajectory from a config dict."""
    traj_type = TrajectoryType.from_string(cfg.get("type", "circular"))
    speed = float(cfg.get("speed_deg_s", 1.5))
    ax    = float(cfg.get("amplitude_x", 1.0))
    ay    = float(cfg.get("amplitude_y", 0.7))
    seed  = int(cfg.get("seed", 42))

    if traj_type == TrajectoryType.LINEAR:
        start_pan = float(cfg.get("start_pan_deg", cfg.get("initial_pan_deg", -1.5)))
        start_tilt = float(cfg.get("start_tilt_deg", cfg.get("initial_tilt_deg", 0.0)))
        vpan = float(cfg.get("vel_pan_deg_s", speed * 0.8))
        vtilt = float(cfg.get("vel_tilt_deg_s", speed * 0.2))
        return StraightLineTrajectory(
            start_pan_deg=start_pan,
            start_tilt_deg=start_tilt,
            vel_pan_deg_s=vpan,
            vel_tilt_deg_s=vtilt,
            size_px=size_px,
            brightness=brightness,
        )
    elif traj_type == TrajectoryType.ACCEPTANCE:
        start_pan = float(cfg.get("start_pan_deg", 1.4))
        start_tilt = float(cfg.get("start_tilt_deg", 1.0))
        return StraightLineTrajectory(
            start_pan_deg=start_pan,
            start_tilt_deg=start_tilt,
            vel_pan_deg_s=0.0,
            vel_tilt_deg_s=0.0,
            size_px=size_px,
            brightness=brightness,
        )
    elif traj_type == TrajectoryType.CIRCULAR:
        return CircularTrajectory(
            amplitude_x_deg=ax, amplitude_y_deg=ay, speed_deg_s=speed,
            size_px=size_px, brightness=brightness)
    elif traj_type == TrajectoryType.FIGURE8:
        return Figure8Trajectory(
            amplitude_x_deg=ax, amplitude_y_deg=ay, speed_deg_s=speed,
            size_px=size_px, brightness=brightness)
    elif traj_type == TrajectoryType.RANDOM:
        return RandomTrajectory(
            amplitude_x_deg=ax, amplitude_y_deg=ay, speed_deg_s=speed,
            seed=seed, size_px=size_px, brightness=brightness)
    else:
        raise ValueError(f"Unknown trajectory type: {traj_type.value}")
