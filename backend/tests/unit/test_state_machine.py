import pytest
from app.core.models import DetectionResult, TrackingState
from app.tracking.state_machine import TrackingStateMachine


def test_state_machine_transition_to_track():
    sm = TrackingStateMachine(acquisition_frames=3, dt=0.033)
    assert sm.state == TrackingState.SEARCH

    valid_det = DetectionResult(detected=True, x=100.0, y=100.0, confidence=0.9, candidate_count=1)

    # Frame 1: SEARCH -> ACQUIRE
    res1 = sm.update(valid_det, timestamp_ms=0.0)
    assert sm.state == TrackingState.ACQUIRE

    # Frame 2: ACQUIRE (count 2)
    res2 = sm.update(valid_det, timestamp_ms=33.3)
    assert sm.state == TrackingState.ACQUIRE

    # Frame 3: ACQUIRE -> TRACK (count 3 reached)
    res3 = sm.update(valid_det, timestamp_ms=66.6)
    assert sm.state == TrackingState.TRACK


def test_state_machine_prediction_and_recovery():
    sm = TrackingStateMachine(acquisition_frames=2, max_prediction_frames=3, dt=0.033)
    valid_det = DetectionResult(detected=True, x=100.0, y=100.0, confidence=0.9, candidate_count=1)
    miss_det = DetectionResult(detected=False, x=None, y=None, confidence=0.0, candidate_count=0)

    # Reach TRACK
    sm.update(valid_det, timestamp_ms=0.0)
    sm.update(valid_det, timestamp_ms=33.3)
    assert sm.state == TrackingState.TRACK

    # Drop 1 frame -> PREDICT
    res_pred = sm.update(miss_det, timestamp_ms=66.6)
    assert sm.state == TrackingState.PREDICT

    # Recover with valid detection -> TRACK
    res_rec = sm.update(valid_det, timestamp_ms=99.9)
    assert sm.state == TrackingState.TRACK
