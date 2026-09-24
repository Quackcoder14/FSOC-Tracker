"""
YAML configuration loader with validation for the FSOC tracking system.
"""

from __future__ import annotations

import copy
import logging
import os
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default configuration — used as a baseline when loading partial YAMLs
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict[str, Any] = {
    "system": {
        "name": "FSOC Coarse Alignment Tracker",
        "target_fps": 30,
        "processing_fps_target": 20,
        "seed": 42,
    },
    "camera": {
        "resolution": {"width": 640, "height": 480},
        "hfov_deg": 4.0,
        "vfov_deg": 3.0,
        "max_pan_speed_deg_s": 5.0,
        "max_tilt_speed_deg_s": 5.0,
        "update_rate_hz": 30,
    },
    "beacon": {
        "size_px": 10,
        "min_size_px": 5,
        "max_size_px": 20,
    },
    "tracking": {
        "acquisition_frames": 3,
        "max_prediction_frames": 12,
        "reacquisition_timeout_ms": 1000,
        "detection_confidence_threshold": 0.50,
    },
    "kalman": {
        "process_noise": 800.0,
        "measurement_noise": 1.5,
        "initial_covariance": 50.0,
    },
    "pid": {
        "pan":  {"kp": 4.5, "ki": 0.12, "kd": 0.30},
        "tilt": {"kp": 4.5, "ki": 0.12, "kd": 0.30},
    },
    "trajectory": {
        "type": "circular",
        "speed_deg_s": 1.5,
        "amplitude_x": 1.0,
        "amplitude_y": 0.7,
        "duration_s": 60,
        "initial_pan_deg": 0.0,
        "initial_tilt_deg": 0.0,
    },
    "disturbances": {
        "gaussian":       {"enabled": False, "sigma": 10},
        "salt_pepper":    {"enabled": False, "probability": 0.05},
        "poisson":        {"enabled": False},
        "blur":           {"enabled": False, "kernel_size": 3},
        "haze":           {"enabled": False, "intensity": 0.3},
        "fog":            {"enabled": False, "intensity": 0.5},
        "rain":           {"enabled": False, "intensity": 0.3},
        "low_light":      {"enabled": False, "gamma": 2.5},
        "camera_jitter":  {"enabled": False, "max_px_per_frame": 5},
        "platform_motion":{"enabled": False, "max_px_per_frame": 5},
        "atmosphere":     {"type": "clear"},
    },
    "performance": {
        "telemetry_hz": 20,
        "benchmark_fps": 30,
    },
    "logging": {
        "level": "INFO",
        "log_to_file": True,
        "log_dir": "logs",
    },
    "ai": {
        "model_path": "models/beacon_validator.onnx",
        "enabled": True,
        "confidence_threshold": 0.7,
        "invoke_on_ambiguous": True,
        "max_candidates_for_ai": 5,
    },
    "output": {
        "results_dir": "results",
        "reports_dir": "reports",
    },
}


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

class ConfigError(ValueError):
    """Raised when configuration is invalid."""
    pass


class Config:
    """Validated configuration object. Access via dict-style or attribute."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def get(self, *args, **kwargs) -> Any:
        """
        Supports both dict-style get(key, default) and multi-key traversal get("a", "b", default=...).
        """
        if not args:
            return kwargs.get("default", None)
        default = kwargs.get("default", None)
        if len(args) == 2 and not isinstance(args[1], str):
            key = args[0]
            default = args[1]
            return self._data.get(key, default)
        elif len(args) == 1:
            return self._data.get(args[0], default)

        d: Any = self._data
        for k in args:
            if not isinstance(d, dict) or k not in d:
                return default
            d = d[k]
        return d

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def items(self):
        return self._data.items()

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def as_dict(self) -> dict:
        return copy.deepcopy(self._data)

    def camera_width(self) -> int:
        return int(self.get("camera", "resolution", "width", default=640))

    def camera_height(self) -> int:
        return int(self.get("camera", "resolution", "height", default=480))

    def hfov(self) -> float:
        return float(self.get("camera", "hfov_deg", default=4.0))

    def vfov(self) -> float:
        return float(self.get("camera", "vfov_deg", default=3.0))

    def seed(self) -> int:
        return int(self.get("system", "seed", default=42))


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    result = copy.deepcopy(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = copy.deepcopy(v)
    return result


def _validate(cfg: dict) -> None:
    """Raise ConfigError on invalid values."""
    cam = cfg.get("camera", {})
    res = cam.get("resolution", {})
    if res.get("width", 0) <= 0:
        raise ConfigError("camera.resolution.width must be > 0")
    if res.get("height", 0) <= 0:
        raise ConfigError("camera.resolution.height must be > 0")
    if cam.get("hfov_deg", 0) <= 0:
        raise ConfigError("camera.hfov_deg must be > 0")
    if cam.get("vfov_deg", 0) <= 0:
        raise ConfigError("camera.vfov_deg must be > 0")

    kalman = cfg.get("kalman", {})
    if kalman.get("process_noise", 0) <= 0:
        raise ConfigError("kalman.process_noise must be > 0")
    if kalman.get("measurement_noise", 0) <= 0:
        raise ConfigError("kalman.measurement_noise must be > 0")

    perf = cfg.get("performance", {})
    if perf.get("telemetry_hz", 0) <= 0:
        raise ConfigError("performance.telemetry_hz must be > 0")


def load_config(path: Optional[str] = None) -> Config:
    """
    Load configuration from YAML file, merging with defaults.
    If path is None, return the default configuration.
    """
    if path is None:
        default_file = configs_dir() / "default.yaml"
        if default_file.exists():
            path = str(default_file)

    base = copy.deepcopy(DEFAULT_CONFIG)

    if path is not None:
        p = Path(path)
        if not p.exists():
            raise ConfigError(f"Configuration file not found: {p}")
        try:
            with p.open("r", encoding="utf-8") as f:
                override = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"YAML parse error in {p}: {e}") from e

        base = _deep_merge(base, override)
        logger.info("Loaded config from: %s", p)
    else:
        logger.info("Using default configuration")

    try:
        _validate(base)
    except ConfigError:
        raise

    return Config(base)


def load_config_from_dict(overrides: dict) -> Config:
    """Create a Config by merging overrides into defaults (for tests)."""
    merged = _deep_merge(DEFAULT_CONFIG, overrides)
    _validate(merged)
    return Config(merged)


def configs_dir() -> Path:
    """Return the path to the configs/ directory relative to this file."""
    return Path(__file__).parent.parent.parent / "configs"
