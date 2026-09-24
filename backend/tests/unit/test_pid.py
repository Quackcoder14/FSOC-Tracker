import pytest
from app.control.pid import PIDController, DualAxisPID


def test_pid_proportional():
    pid = PIDController(kp=2.0, ki=0.0, kd=0.0, output_limits=(-10.0, 10.0))
    out = pid.update(error=3.0, dt=0.1)
    assert out == pytest.approx(6.0)


def test_pid_integral_and_antiwindup():
    pid = PIDController(kp=0.0, ki=1.0, kd=0.0, output_limits=(-5.0, 5.0), integral_limits=(-4.0, 4.0))
    # Accumulate
    pid.update(error=10.0, dt=1.0)
    # Integral should clamp to 4.0
    telemetry = pid.get_telemetry()
    assert telemetry["integral"] == pytest.approx(4.0)
    assert telemetry["output"] == pytest.approx(4.0)


def test_pid_derivative():
    pid = PIDController(kp=0.0, ki=0.0, kd=0.5, output_limits=(-10.0, 10.0))
    # First step: prev_error is None, derivative is 0
    pid.update(error=2.0, dt=1.0)
    # Second step: error increases by 4.0 over 1.0s -> rate = 4.0 -> d_term = 0.5 * 4.0 = 2.0
    out = pid.update(error=6.0, dt=1.0)
    assert out == pytest.approx(2.0)


def test_dual_axis_pid():
    pan_cfg = {"kp": 1.0, "ki": 0.0, "kd": 0.0}
    tilt_cfg = {"kp": 2.0, "ki": 0.0, "kd": 0.0}
    controller = DualAxisPID(pan_cfg, tilt_cfg, max_pan_speed=5.0, max_tilt_speed=5.0)

    pan_cmd, tilt_cmd = controller.update(error_x_deg=2.0, error_y_deg=1.5, dt=0.1)
    assert pan_cmd == pytest.approx(2.0)
    assert tilt_cmd == pytest.approx(3.0)
