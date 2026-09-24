"""
Disturbance engine — composable image disturbance modules for FSOC simulation.
All disturbances implement Disturbance.apply(frame, context) -> ndarray.
"""

from __future__ import annotations

import copy
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping

import cv2
import numpy as np

from app.core.models import DisturbanceState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class Disturbance(ABC):
    @abstractmethod
    def apply(self, image: np.ndarray, context: dict) -> np.ndarray:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


# ---------------------------------------------------------------------------
# Individual disturbances
# ---------------------------------------------------------------------------

class GaussianNoise(Disturbance):
    name = "gaussian"

    def __init__(self, sigma: float = 10.0) -> None:
        self.sigma = sigma

    def apply(self, image: np.ndarray, context: dict) -> np.ndarray:
        rng: np.random.Generator = context.get("rng", np.random.default_rng())
        noise = rng.normal(0, self.sigma, image.shape).astype(np.float32)
        return np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)


class SaltPepperNoise(Disturbance):
    name = "salt_pepper"

    def __init__(self, probability: float = 0.05) -> None:
        self.probability = probability

    def apply(self, image: np.ndarray, context: dict) -> np.ndarray:
        rng: np.random.Generator = context.get("rng", np.random.default_rng())
        out = image.copy()
        mask = rng.random(image.shape[:2])
        out[mask < self.probability / 2] = 0
        out[mask > 1 - self.probability / 2] = 255
        return out


class PoissonNoise(Disturbance):
    name = "poisson"

    def apply(self, image: np.ndarray, context: dict) -> np.ndarray:
        rng: np.random.Generator = context.get("rng", np.random.default_rng())
        scaled = image.astype(np.float32) / 255.0 * 10.0
        noisy = rng.poisson(scaled.clip(0)) / 10.0 * 255.0
        return np.clip(noisy, 0, 255).astype(np.uint8)


class BlurDisturbance(Disturbance):
    name = "blur"

    def __init__(self, kernel_size: int = 3) -> None:
        self.kernel_size = kernel_size if kernel_size % 2 == 1 else kernel_size + 1

    def apply(self, image: np.ndarray, context: dict) -> np.ndarray:
        return cv2.GaussianBlur(image, (self.kernel_size, self.kernel_size), 0)


class HazeDisturbance(Disturbance):
    """Reduces image contrast and adds a bright overlay (atmospheric scattering)."""
    name = "haze"

    def __init__(self, intensity: float = 0.3) -> None:
        self.intensity = float(np.clip(intensity, 0, 1))

    def apply(self, image: np.ndarray, context: dict) -> np.ndarray:
        haze_val = int(200 * self.intensity)
        overlay = np.full(image.shape, haze_val, dtype=np.float32)
        out = image.astype(np.float32) * (1 - self.intensity) + overlay * self.intensity
        return np.clip(out, 0, 255).astype(np.uint8)


class FogDisturbance(Disturbance):
    """Dense haze with additional blur."""
    name = "fog"

    def __init__(self, intensity: float = 0.5) -> None:
        self.intensity = float(np.clip(intensity, 0, 1))
        self._haze = HazeDisturbance(intensity)
        self._blur = BlurDisturbance(kernel_size=9)

    def apply(self, image: np.ndarray, context: dict) -> np.ndarray:
        out = self._haze.apply(image, context)
        out = self._blur.apply(out, context)
        return out


class RainDisturbance(Disturbance):
    """Simulates rain streaks."""
    name = "rain"

    def __init__(self, intensity: float = 0.3) -> None:
        self.intensity = float(np.clip(intensity, 0, 1))
        self.n_streaks = int(200 * intensity)

    def apply(self, image: np.ndarray, context: dict) -> np.ndarray:
        rng: np.random.Generator = context.get("rng", np.random.default_rng())
        out = image.copy()
        h, w = out.shape[:2]
        for _ in range(self.n_streaks):
            x0 = int(rng.integers(0, w))
            y0 = int(rng.integers(0, h))
            length = int(rng.integers(5, 20))
            x1 = int(np.clip(x0 + rng.integers(-2, 2), 0, w - 1))
            y1 = int(np.clip(y0 + length, 0, h - 1))
            brightness = int(rng.integers(140, 200))
            cv2.line(out, (x0, y0), (x1, y1), (brightness, brightness, brightness), 1)
        return out


class LowLightDisturbance(Disturbance):
    """Gamma compression to simulate low-light conditions."""
    name = "low_light"

    def __init__(self, gamma: float = 2.5) -> None:
        self.gamma = max(gamma, 0.1)
        table = np.array(
            [(i / 255.0) ** self.gamma * 255 for i in range(256)],
            dtype=np.uint8,
        )
        self._lut = table

    def apply(self, image: np.ndarray, context: dict) -> np.ndarray:
        return cv2.LUT(image, self._lut)


class CameraJitter(Disturbance):
    """
    Simulates camera vibration by randomly shifting the frame.
    The jitter offset is returned in context["jitter_x"], context["jitter_y"]
    for use by the target generator.
    """
    name = "camera_jitter"

    def __init__(self, max_px_per_frame: float = 5.0) -> None:
        self.max_px = max_px_per_frame

    def apply(self, image: np.ndarray, context: dict) -> np.ndarray:
        rng: np.random.Generator = context.get("rng", np.random.default_rng())
        dx = float(rng.uniform(-self.max_px, self.max_px))
        dy = float(rng.uniform(-self.max_px, self.max_px))
        context["jitter_x"] = dx
        context["jitter_y"] = dy

        h, w = image.shape[:2]
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        return cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_REFLECT)


class PlatformMotion(Disturbance):
    """
    Simulates platform vibration with a smoothed random offset.
    """
    name = "platform_motion"

    def __init__(self, max_px_per_frame: float = 5.0) -> None:
        self.max_px = max_px_per_frame
        self._prev_dx = 0.0
        self._prev_dy = 0.0

    def apply(self, image: np.ndarray, context: dict) -> np.ndarray:
        rng: np.random.Generator = context.get("rng", np.random.default_rng())
        target_dx = float(rng.uniform(-self.max_px, self.max_px))
        target_dy = float(rng.uniform(-self.max_px, self.max_px))
        alpha = 0.4
        dx = alpha * target_dx + (1 - alpha) * self._prev_dx
        dy = alpha * target_dy + (1 - alpha) * self._prev_dy
        self._prev_dx, self._prev_dy = dx, dy
        context["platform_motion_x"] = dx
        context["platform_motion_y"] = dy

        h, w = image.shape[:2]
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        return cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_REFLECT)


# ---------------------------------------------------------------------------
# Typed disturbance configuration
# ---------------------------------------------------------------------------

@dataclass
class DisturbanceConfig:
    """Internal typed configuration for the disturbance engine."""
    gaussian_enabled: bool = False
    gaussian_sigma: float = 10.0

    salt_pepper_enabled: bool = False
    salt_pepper_probability: float = 0.05

    poisson_enabled: bool = False

    blur_enabled: bool = False
    blur_kernel_size: int = 3

    atmosphere_type: str = "clear"
    atmosphere_intensity: float = 0.3

    low_light_enabled: bool = False
    low_light_gamma: float = 2.5

    camera_jitter_enabled: bool = False
    camera_jitter_max_px: float = 5.0

    platform_motion_enabled: bool = False
    platform_motion_max_px: float = 5.0

    @staticmethod
    def from_dict(cfg: Mapping[str, Any]) -> "DisturbanceConfig":
        """Create DisturbanceConfig from a disturbances dict (raw YAML/WS payload)."""
        d = cfg.get("disturbances", {}) if isinstance(cfg, Mapping) else {}

        def get_bool(key: str, default: bool = False) -> bool:
            v = d.get(key, {})
            if isinstance(v, dict):
                return bool(v.get("enabled", default))
            return default

        def get_float(key: str, subkey: str, default: float) -> float:
            v = d.get(key, {})
            if isinstance(v, dict):
                return float(v.get(subkey, default))
            return default

        def get_int(key: str, subkey: str, default: int) -> int:
            v = d.get(key, {})
            if isinstance(v, dict):
                return int(v.get(subkey, default))
            return default

        atm = d.get("atmosphere", {})
        atm_type = "clear"
        atm_intensity = 0.3
        if isinstance(atm, dict):
            atm_type = str(atm.get("type", "clear")).lower()
            atm_intensity = float(atm.get("intensity", 0.3))

        return DisturbanceConfig(
            gaussian_enabled=get_bool("gaussian"),
            gaussian_sigma=get_float("gaussian", "sigma", 10.0),

            salt_pepper_enabled=get_bool("salt_pepper"),
            salt_pepper_probability=get_float("salt_pepper", "probability", 0.05),

            poisson_enabled=get_bool("poisson"),

            blur_enabled=get_bool("blur"),
            blur_kernel_size=get_int("blur", "kernel_size", 3),

            atmosphere_type=atm_type,
            atmosphere_intensity=atm_intensity,

            low_light_enabled=get_bool("low_light"),
            low_light_gamma=get_float("low_light", "gamma", 2.5),

            camera_jitter_enabled=get_bool("camera_jitter"),
            camera_jitter_max_px=get_float("camera_jitter", "max_px_per_frame", 5.0),

            platform_motion_enabled=get_bool("platform_motion"),
            platform_motion_max_px=get_float("platform_motion", "max_px_per_frame", 5.0),
        )

    def to_dict(self) -> dict:
        """Serialize to dict for telemetry/echo."""
        return {
            "gaussian": {"enabled": self.gaussian_enabled, "sigma": self.gaussian_sigma},
            "salt_pepper": {"enabled": self.salt_pepper_enabled, "probability": self.salt_pepper_probability},
            "poisson": {"enabled": self.poisson_enabled},
            "blur": {"enabled": self.blur_enabled, "kernel_size": self.blur_kernel_size},
            "atmosphere": {"type": self.atmosphere_type, "intensity": self.atmosphere_intensity},
            "low_light": {"enabled": self.low_light_enabled, "gamma": self.low_light_gamma},
            "camera_jitter": {"enabled": self.camera_jitter_enabled, "max_px_per_frame": self.camera_jitter_max_px},
            "platform_motion": {"enabled": self.platform_motion_enabled, "max_px_per_frame": self.platform_motion_max_px},
        }


# ---------------------------------------------------------------------------
# Disturbance Engine
# ---------------------------------------------------------------------------

class DisturbanceEngine:
    """
    Manages and applies a pipeline of disturbance modules.
    Order matters: camera jitter and platform motion are applied last
    so the geometric shift affects the complete rendered image.
    """

    # Fixed application order
    _ORDER = [
        "low_light", "gaussian", "salt_pepper", "poisson",
        "haze", "fog", "rain", "blur",
        "platform_motion", "camera_jitter",
    ]

    def __init__(self, cfg: Mapping[str, Any], seed: int = 42) -> None:
        self._seed = seed
        self._rng = np.random.default_rng(seed)
        self._modules: dict[str, Disturbance] = {}
        self._config = DisturbanceConfig.from_dict(cfg)
        self._build()

    def _build(self) -> None:
        """Rebuild the active module pipeline from current internal config."""
        self._modules.clear()

        if self._config.gaussian_enabled:
            self._modules["gaussian"] = GaussianNoise(sigma=self._config.gaussian_sigma)

        if self._config.salt_pepper_enabled:
            self._modules["salt_pepper"] = SaltPepperNoise(probability=self._config.salt_pepper_probability)

        if self._config.poisson_enabled:
            self._modules["poisson"] = PoissonNoise()

        if self._config.blur_enabled:
            self._modules["blur"] = BlurDisturbance(kernel_size=self._config.blur_kernel_size)

        atm = self._config.atmosphere_type.lower()
        if atm == "haze" or self._config.atmosphere_type == "haze":
            self._modules["haze"] = HazeDisturbance(intensity=self._config.atmosphere_intensity)
        elif atm == "fog":
            self._modules["fog"] = FogDisturbance(intensity=self._config.atmosphere_intensity)
        elif atm == "rain":
            self._modules["rain"] = RainDisturbance(intensity=self._config.atmosphere_intensity)

        if self._config.low_light_enabled:
            self._modules["low_light"] = LowLightDisturbance(gamma=self._config.low_light_gamma)

        if self._config.platform_motion_enabled:
            self._modules["platform_motion"] = PlatformMotion(
                max_px_per_frame=self._config.platform_motion_max_px)

        if self._config.camera_jitter_enabled:
            self._modules["camera_jitter"] = CameraJitter(
                max_px_per_frame=self._config.camera_jitter_max_px)

        logger.info("DisturbanceEngine active modules: %s", list(self._modules.keys()))

    def apply(self, image: np.ndarray, frame_index: int = 0) -> tuple[np.ndarray, dict]:
        """Apply all enabled disturbances in deterministic order."""
        context: dict = {
            "frame_index": frame_index,
            "rng": self._rng,
            "jitter_x": 0.0,
            "jitter_y": 0.0,
            "platform_motion_x": 0.0,
            "platform_motion_y": 0.0,
        }

        out = image
        for key in self._ORDER:
            if key in self._modules:
                out = self._modules[key].apply(out, context)

        return out, context

    def get_state(self) -> DisturbanceState:
        """Return current disturbance state for telemetry."""
        return DisturbanceState(
            enabled=bool(self._modules),
            gaussian_enabled="gaussian" in self._modules,
            gaussian_sigma=self._config.gaussian_sigma if self._config.gaussian_enabled else 0.0,
            salt_pepper_enabled="salt_pepper" in self._modules,
            salt_pepper_probability=self._config.salt_pepper_probability if self._config.salt_pepper_enabled else 0.0,
            poisson_enabled="poisson" in self._modules,
            atmosphere_type=self._config.atmosphere_type,
            low_light_enabled="low_light" in self._modules,
            blur_enabled="blur" in self._modules,
            camera_jitter_x=self._config.camera_jitter_max_px if self._config.camera_jitter_enabled else 0.0,
            camera_jitter_y=self._config.camera_jitter_max_px if self._config.camera_jitter_enabled else 0.0,
            platform_motion_x=self._config.platform_motion_max_px if self._config.platform_motion_enabled else 0.0,
            platform_motion_y=self._config.platform_motion_max_px if self._config.platform_motion_enabled else 0.0,
        )

    def get_config(self) -> DisturbanceConfig:
        """Return a copy of the current internal configuration."""
        return copy.deepcopy(self._config)

    def configure(self, overrides: Mapping[str, Any]) -> None:
        """Public alias for update_from_dict(). Preferred external entry point."""
        self.update_from_dict(overrides)

    def update_from_dict(self, overrides: Mapping[str, Any]) -> None:
        """
        Update disturbance parameters at runtime (from UI commands).

        Atomic update: validate incoming settings, construct new valid state,
        then commit. If validation fails, do NOT partially mutate existing config.

        Key normalization applied:
          - camera_jitter.max_px  → camera_jitter.max_px_per_frame
          - platform_motion.max_px → platform_motion.max_px_per_frame
        This allows the frontend to use the shorter 'max_px' form.
        """
        # Normalize abbreviated keys that differ between frontend and config schema
        normalized: dict[str, Any] = {}
        for k, v in overrides.items():
            if k in ("camera_jitter", "platform_motion") and isinstance(v, Mapping):
                v = dict(v)
                if "max_px" in v and "max_px_per_frame" not in v:
                    v["max_px_per_frame"] = v.pop("max_px")
            normalized[k] = v

        # Build a candidate new config by merging overrides into current
        candidate = copy.deepcopy(self._config)

        # Helper to safely set nested attributes
        def set_nested(obj: Any, path: list[str], value: Any) -> None:
            for p in path[:-1]:
                obj = getattr(obj, p)
            setattr(obj, path[-1], value)

        # Mapping from override keys to config attributes
        key_mapping = {
            "gaussian": [
                ("gaussian_enabled", lambda d: bool(d.get("enabled", False))),
                ("gaussian_sigma", lambda d: float(d.get("sigma", candidate.gaussian_sigma))),
            ],
            "salt_pepper": [
                ("salt_pepper_enabled", lambda d: bool(d.get("enabled", False))),
                ("salt_pepper_probability", lambda d: float(d.get("probability", candidate.salt_pepper_probability))),
            ],
            "poisson": [
                ("poisson_enabled", lambda d: bool(d.get("enabled", False))),
            ],
            "blur": [
                ("blur_enabled", lambda d: bool(d.get("enabled", False))),
                ("blur_kernel_size", lambda d: int(d.get("kernel_size", candidate.blur_kernel_size))),
            ],
            "atmosphere": [
                ("atmosphere_type", lambda d: str(d.get("type", candidate.atmosphere_type)).lower()),
                ("atmosphere_intensity", lambda d: float(np.clip(d.get("intensity", candidate.atmosphere_intensity), 0, 1))),
            ],
            "low_light": [
                ("low_light_enabled", lambda d: bool(d.get("enabled", False))),
                ("low_light_gamma", lambda d: float(max(d.get("gamma", candidate.low_light_gamma), 0.1))),
            ],
            "camera_jitter": [
                ("camera_jitter_enabled", lambda d: bool(d.get("enabled", False))),
                ("camera_jitter_max_px", lambda d: float(max(d.get("max_px_per_frame", candidate.camera_jitter_max_px), 0.0))),
            ],
            "platform_motion": [
                ("platform_motion_enabled", lambda d: bool(d.get("enabled", False))),
                ("platform_motion_max_px", lambda d: float(max(d.get("max_px_per_frame", candidate.platform_motion_max_px), 0.0))),
            ],
        }

        # Apply overrides with validation
        for key, attr_setters in key_mapping.items():
            if key in normalized:
                val = normalized[key]
                if not isinstance(val, Mapping):
                    continue
                for attr_name, extractor in attr_setters:
                    try:
                        new_val = extractor(val)
                        setattr(candidate, attr_name, new_val)
                    except (ValueError, TypeError) as e:
                        raise ValueError(f"Invalid value for {key}.{attr_name}: {e}") from e

        # Validate atmosphere type
        valid_atmospheres = {"clear", "haze", "fog", "rain"}
        if candidate.atmosphere_type not in valid_atmospheres:
            raise ValueError(f"Invalid atmosphere type: {candidate.atmosphere_type}. Must be one of {valid_atmospheres}")

        # Validate blur kernel size is odd
        if candidate.blur_enabled and candidate.blur_kernel_size % 2 == 0:
            candidate.blur_kernel_size += 1

        # All validations passed — commit the new config
        self._config = candidate
        self._build()
        logger.info("DisturbanceEngine reconfigured — active: %s", list(self._modules.keys()))