import pytest
from app.core.models import TrackingResult, TrackingState
from app.evaluation.ground_truth import GroundTruthPoint
from app.evaluation.metrics import MetricsAccumulator


def test_metrics_accumulator():
    metrics = MetricsAccumulator()
    
    # Simulate 3 frames with known error
    gt1 = GroundTruthPoint(0, 0.0, 100.0, 100.0)
    res1 = TrackingResult(103.0, 104.0, 103.0, 104.0, 0.0, 0.0, 1.0, TrackingState.TRACK)
    # Error = hypot(3, 4) = 5.0
    m_out = metrics.update(0, 0.0, res1, True, gt_point=gt1, processing_time_ms=5.0)

    assert m_out.instantaneous_error_px == pytest.approx(5.0)
    assert m_out.rmse_px == pytest.approx(5.0)
    assert m_out.lock_retention_percent == pytest.approx(100.0)

    summary = metrics.get_summary()
    assert summary["rmse_px"] == pytest.approx(5.0)
    assert summary["total_frames"] == 1
    assert summary["frames_tracked"] == 1
