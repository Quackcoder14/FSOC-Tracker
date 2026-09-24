from __future__ import annotations

import numpy as np
import pytest

from app.simulation.disturbances import DisturbanceEngine, DisturbanceState


def _make_cfg(disturbances_dict: dict | None = None) -> dict:
    return {
        "system": {"seed": 42},
        "disturbances": disturbances_dict or {},
    }


def test_gaussian_enabled_and_disabled():
    # Disabled
    engine_off = DisturbanceEngine(_make_cfg({"gaussian": {"enabled": False, "sigma": 15}}))
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    out_off, _ = engine_off.apply(img.copy(), frame_index=0)
    assert np.all(out_off == 0)

    # Enabled
    engine_on = DisturbanceEngine(_make_cfg({"gaussian": {"enabled": True, "sigma": 20}}))
    out_on, _ = engine_on.apply(img.copy(), frame_index=0)
    assert not np.all(out_on == 0)
    assert out_on.mean() > 0


def test_salt_pepper_enabled():
    engine = DisturbanceEngine(_make_cfg({"salt_pepper": {"enabled": True, "probability": 0.05}}))
    img = np.full((100, 100, 3), 128, dtype=np.uint8)
    out, _ = engine.apply(img.copy(), frame_index=0)
    # Check that some pixels became 0 or 255
    has_extremes = np.any(out == 0) or np.any(out == 255)
    assert has_extremes


def test_atmosphere_modes():
    # Haze
    engine_haze = DisturbanceEngine(_make_cfg({"atmosphere": {"type": "haze", "intensity": 0.4}}))
    img = np.full((50, 50, 3), 50, dtype=np.uint8)
    out_haze, _ = engine_haze.apply(img.copy(), frame_index=0)
    assert out_haze.mean() > 50  # Haze adds luminance/veiling light

    # Fog
    engine_fog = DisturbanceEngine(_make_cfg({"atmosphere": {"type": "fog", "intensity": 0.5}}))
    out_fog, _ = engine_fog.apply(img.copy(), frame_index=0)
    assert out_fog.mean() > 50

    # Rain
    engine_rain = DisturbanceEngine(_make_cfg({"atmosphere": {"type": "rain", "intensity": 0.3}}))
    out_rain, _ = engine_rain.apply(img.copy(), frame_index=0)
    assert out_rain.mean() > 50


def test_blur_enabled():
    engine = DisturbanceEngine(_make_cfg({"blur": {"enabled": True, "kernel_size": 5}}))
    img = np.zeros((50, 50, 3), dtype=np.uint8)
    img[25, 25] = [255, 255, 255]
    out, _ = engine.apply(img.copy(), frame_index=0)
    # The center impulse should be spread to neighboring pixels
    assert out[25, 25, 0] < 255
    assert out[24, 25, 0] > 0


def test_jitter_and_platform_motion():
    engine = DisturbanceEngine(_make_cfg({
        "camera_jitter": {"enabled": True, "max_px_per_frame": 4.0},
        "platform_motion": {"enabled": True, "max_px_per_frame": 3.0},
    }))
    img = np.zeros((50, 50, 3), dtype=np.uint8)
    _, ctx = engine.apply(img.copy(), frame_index=1)
    assert "jitter_x" in ctx
    assert "jitter_y" in ctx
    assert "platform_motion_x" in ctx
    assert "platform_motion_y" in ctx


def test_dynamic_update_and_key_normalization():
    # Start with all disabled
    engine = DisturbanceEngine(_make_cfg({}))
    img = np.zeros((50, 50, 3), dtype=np.uint8)
    out1, _ = engine.apply(img.copy(), frame_index=0)
    assert np.all(out1 == 0)

    # Reconfigure via update_from_dict with abbreviated max_px
    engine.update_from_dict({
        "gaussian": {"enabled": True, "sigma": 15},
        "camera_jitter": {"enabled": True, "max_px": 5},
    })
    state = engine.get_state()
    assert state.gaussian_enabled
    assert state.gaussian_sigma == 15
    assert state.camera_jitter_x == 5

    out2, ctx2 = engine.apply(img.copy(), frame_index=1)
    assert not np.all(out2 == 0)
    assert "jitter_x" in ctx2


def test_configure_alias():
    engine = DisturbanceEngine(_make_cfg({}))
    engine.configure({"salt_pepper": {"enabled": True, "probability": 0.02}})
    state = engine.get_state()
    assert state.salt_pepper_enabled
    assert state.salt_pepper_probability == 0.02
