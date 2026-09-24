import numpy as np
import pytest
from app.tracking.kalman import KalmanTracker


def test_kalman_initialization():
    tracker = KalmanTracker()
    assert not tracker.initialized

    tracker.initialize(100.0, 200.0)
    assert tracker.initialized
    pos = tracker.position
    assert pos == (100.0, 200.0)
    vel = tracker.velocity
    assert vel == (0.0, 0.0)


def test_kalman_prediction():
    tracker = KalmanTracker()
    tracker.initialize(100.0, 200.0)
    # Give it a velocity by updating with a step
    tracker.update(105.0, 200.0)
    
    # Predict next state
    pred_x, pred_y = tracker.predict(dt=1.0)
    assert pred_x > 100.0
    assert pred_y == pytest.approx(200.0, abs=1.0)


def test_kalman_reset():
    tracker = KalmanTracker()
    tracker.initialize(50.0, 50.0)
    assert tracker.initialized
    tracker.reset()
    assert not tracker.initialized
