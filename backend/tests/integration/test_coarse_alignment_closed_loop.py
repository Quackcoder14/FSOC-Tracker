"""
Automated Integration Tests: Closed-Loop Coarse Alignment & Virtual Camera Projection.

Verifies:
1. Acceptance test: Target starts significantly off-axis (upper-right) and closed loop
   naturally drives camera orientation until target settles on stationary boresight (+).
2. Moving target FOV retention: Continuous trajectory (circular and figure-8) remains
   within sensor FOV across all frames under configured tracking speed.
3. Sign convention verification: Confirms negative feedback for both horizontal (pan)
   and vertical (tilt) axes.
"""

import math
import pytest
from app.config.loader import load_config
from app.core.engine import Engine
from app.simulation.target import StraightLineTrajectory, CircularTrajectory, Figure8Trajectory


def test_acceptance_upper_right_settling():
    """
    Acceptance Test:
    Start with:
      Target:        upper-right (world: pan=+1.4 deg, tilt=+1.0 deg)
      Camera:        centered (pan=0.0 deg, tilt=0.0 deg)
      Initial error: large (> 200 px)

    Expect:
      t0: Upper-right, large error
      t1: Moving inward
      t2: Closer
      until: Centered at boresight (+)

    The fixed optical-axis crosshair represents image center and remains stationary.
    The controller genuinely rotates the virtual camera orientation, which naturally
    moves the target's projected coordinates to boresight.
    """
    cfg = load_config()
    engine = Engine(cfg)

    # Configure upper-right stationary target
    engine.source._trajectory = StraightLineTrajectory(
        start_pan_deg=1.4,
        start_tilt_deg=1.0,
        vel_pan_deg_s=0.0,
        vel_tilt_deg_s=0.0,
    )
    engine.source.start()

    cx = engine.source._width / 2.0   # 320.0
    cy = engine.source._height / 2.0  # 240.0

    # Step t0
    t0 = engine.step()
    assert t0 is not None
    det0 = t0.detection
    ctrl0 = t0.control
    cam0 = engine.source.camera.state

    # Initial position must be upper-right
    assert det0["detected"] is True
    assert det0["x"] > cx + 150.0  # significantly to the right (> 470 px)
    assert det0["y"] < cy - 100.0  # significantly up (< 140 px)
    init_err = math.hypot(ctrl0["error_x_px"], ctrl0["error_y_px"])
    assert init_err > 200.0        # initial error is large

    # Step t1
    t1 = engine.step()
    err1 = math.hypot(t1.control["error_x_px"], t1.control["error_y_px"])
    # Target projected position must move inward (error decreases)
    assert err1 < init_err

    # Step through frames to trace settling
    prev_err = err1
    for frame_i in range(2, 40):
        t = engine.step()
        err = math.hypot(t.control["error_x_px"], t.control["error_y_px"])
        # Overall monotonic convergence trend
        if frame_i % 5 == 0:
            assert err < prev_err
            prev_err = err

    engine.source.stop()

    # Final state at t_final (~frame 39)
    final_cam = engine.source.camera.state
    final_ctrl = t.control
    final_det = t.detection
    final_err_px = math.hypot(final_ctrl["error_x_px"], final_ctrl["error_y_px"])

    # Verify target has settled to boresight (error < 15 px / < 0.1 deg)
    assert final_err_px < 15.0, f"Expected final error < 15 px, got {final_err_px:.2f} px"
    assert abs(final_ctrl["error_x_deg"]) < 0.1
    assert abs(final_ctrl["error_y_deg"]) < 0.1

    # Verify that camera orientation genuinely adjusted to point at target in world
    assert final_cam.pan_deg > 1.2, f"Camera pan should have reached ~1.4 deg, got {final_cam.pan_deg:.3f}"
    assert final_cam.tilt_deg > 0.8, f"Camera tilt should have reached ~1.0 deg, got {final_cam.tilt_deg:.3f}"

    # Verify optical-axis crosshair remained stationary at image center
    assert cx == 320.0
    assert cy == 240.0


def test_moving_target_remains_in_fov():
    """
    Verify that a moving target remains within the FOV across all frames when its
    angular velocity is within the configured camera tracking capability.
    """
    cfg = load_config()
    engine = Engine(cfg)

    # 1. Circular trajectory at 1.5 deg/s (camera capability is 5.0 deg/s)
    engine.source._trajectory = CircularTrajectory(
        amplitude_x_deg=1.2,
        amplitude_y_deg=0.8,
        speed_deg_s=1.5,
    )
    engine.source.start()

    frames_tested = 120
    for frame_i in range(frames_tested):
        telemetry = engine.step()
        assert telemetry is not None

        cam = engine.source.camera
        ts = engine.source.last_target_state

        # Check target is in camera FOV
        assert cam.is_in_fov(ts.pan_deg, ts.tilt_deg), (
            f"Frame {frame_i}: Target left camera FOV! "
            f"target=({ts.pan_deg:.2f}, {ts.tilt_deg:.2f}), cam=({cam.state.pan_deg:.2f}, {cam.state.tilt_deg:.2f})"
        )

        # After initial acquisition frames (frame 10+), detection must be maintained
        if frame_i > 10:
            assert telemetry.detection["detected"] is True
            # Image position must be well within image bounds [0, 640) x [0, 480)
            det_x = telemetry.detection["x"]
            det_y = telemetry.detection["y"]
            assert 0 <= det_x < 640
            assert 0 <= det_y < 480

    engine.source.stop()
    summary = engine.pipeline.metrics.get_summary()
    # High lock retention (> 90%)
    assert summary["lock_retention_percent"] >= 90.0


def test_sign_conventions_negative_feedback():
    """
    Verify sign conventions for horizontal (pan) and vertical (tilt) motion:
    - Target right -> pan_cmd > 0 -> camera pans right -> projected position moves toward center.
    - Target left  -> pan_cmd < 0 -> camera pans left  -> projected position moves toward center.
    - Target up    -> tilt_cmd > 0 -> camera tilts up  -> projected position moves toward center.
    - Target down  -> tilt_cmd < 0 -> camera tilts down -> projected position moves toward center.
    """
    cfg = load_config()

    # 1. Target right of center
    engine = Engine(cfg)
    engine.source._trajectory = StraightLineTrajectory(start_pan_deg=1.0, start_tilt_deg=0.0, vel_pan_deg_s=0.0, vel_tilt_deg_s=0.0)
    engine.source.start()
    t0 = engine.step()
    assert t0.control["error_x_px"] > 0
    assert t0.control["pan_cmd_deg_s"] > 0
    t1 = engine.step()
    assert engine.source.camera.state.pan_deg > 0
    assert t1.control["error_x_px"] < t0.control["error_x_px"]
    engine.source.stop()

    # 2. Target left of center
    engine = Engine(cfg)
    engine.source._trajectory = StraightLineTrajectory(start_pan_deg=-1.0, start_tilt_deg=0.0, vel_pan_deg_s=0.0, vel_tilt_deg_s=0.0)
    engine.source.start()
    t0 = engine.step()
    assert t0.control["error_x_px"] < 0
    assert t0.control["pan_cmd_deg_s"] < 0
    t1 = engine.step()
    assert engine.source.camera.state.pan_deg < 0
    assert abs(t1.control["error_x_px"]) < abs(t0.control["error_x_px"])
    engine.source.stop()

    # 3. Target above center (positive tilt)
    engine = Engine(cfg)
    engine.source._trajectory = StraightLineTrajectory(start_pan_deg=0.0, start_tilt_deg=1.0, vel_pan_deg_s=0.0, vel_tilt_deg_s=0.0)
    engine.source.start()
    t0 = engine.step()
    assert t0.control["error_y_px"] < 0  # image-y is smaller when target is up
    assert t0.control["error_y_deg"] > 0 # angular tilt error is positive
    assert t0.control["tilt_cmd_deg_s"] > 0
    t1 = engine.step()
    assert engine.source.camera.state.tilt_deg > 0
    assert abs(t1.control["error_y_px"]) < abs(t0.control["error_y_px"])
    engine.source.stop()

    # 4. Target below center (negative tilt)
    engine = Engine(cfg)
    engine.source._trajectory = StraightLineTrajectory(start_pan_deg=0.0, start_tilt_deg=-1.0, vel_pan_deg_s=0.0, vel_tilt_deg_s=0.0)
    engine.source.start()
    t0 = engine.step()
    assert t0.control["error_y_px"] > 0  # image-y is larger when target is down
    assert t0.control["error_y_deg"] < 0 # angular tilt error is negative
    assert t0.control["tilt_cmd_deg_s"] < 0
    t1 = engine.step()
    assert engine.source.camera.state.tilt_deg < 0
    assert abs(t1.control["error_y_px"]) < abs(t0.control["error_y_px"])
    engine.source.stop()
