import pytest
from app.config.loader import load_config
from app.core.engine import Engine


def test_closed_loop_tracking_pipeline():
    cfg = load_config()
    engine = Engine(cfg)
    engine.source.start()

    # Step through 30 frames
    last_telemetry = None
    for _ in range(30):
        last_telemetry = engine.step()

    engine.source.stop()

    assert last_telemetry is not None
    summary = engine.pipeline.metrics.get_summary()

    # Verify key requirements
    assert summary["total_frames"] == 30
    assert summary["frames_tracked"] >= 20
    assert summary["lock_retention_percent"] >= 80.0
    assert summary["rmse_px"] is not None
    assert summary["rmse_px"] < 10.0  # Spec is <= 10 px
