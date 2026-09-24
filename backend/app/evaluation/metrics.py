"""
Performance metrics evaluation engine for FSOC tracking.

Computes RMSE, acquisition latency, lock retention, and pipeline throughput.
"""

from __future__ import annotations

import logging
import math
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

from app.core.models import TrackingResult, TrackingState, MetricsResult
from app.evaluation.ground_truth import GroundTruthPoint

logger = logging.getLogger(__name__)


class MetricsAccumulator:
    """
    Accumulates frame-by-frame tracking and timing metrics across a run.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.errors_px: List[float] = []
        self.frame_latencies_ms: List[float] = []
        
        self.total_frames: int = 0
        self.frames_tracked: int = 0
        self.frames_detected: int = 0
        self.frames_lost: int = 0
        
        self.target_loss_count: int = 0
        self.first_track_timestamp_ms: Optional[float] = None
        self.start_timestamp_ms: Optional[float] = None
        
        self._prev_state: TrackingState = TrackingState.SEARCH
        self._lost_start_ms: Optional[float] = None
        self.reacquisition_times_ms: List[float] = []

    def update(
        self,
        frame_index: int,
        timestamp_ms: float,
        tracking_result: TrackingResult,
        detected: bool,
        gt_point: Optional[GroundTruthPoint] = None,
        processing_time_ms: float = 0.0,
    ) -> MetricsResult:
        """
        Processes one frame's tracking output and updates metrics.
        """
        self.total_frames += 1
        self.frame_latencies_ms.append(processing_time_ms)

        if self.start_timestamp_ms is None:
            self.start_timestamp_ms = timestamp_ms

        curr_state = tracking_result.state
        if detected:
            self.frames_detected += 1
        else:
            self.frames_lost += 1

        if curr_state == TrackingState.TRACK:
            self.frames_tracked += 1
            if self.first_track_timestamp_ms is None:
                self.first_track_timestamp_ms = timestamp_ms - (self.start_timestamp_ms or 0.0)
            
            # Check if re-acquired after being lost
            if self._lost_start_ms is not None:
                reacq_time = timestamp_ms - self._lost_start_ms
                self.reacquisition_times_ms.append(reacq_time)
                self._lost_start_ms = None

        elif self._prev_state == TrackingState.TRACK and curr_state != TrackingState.TRACK:
            # Transitioned out of TRACK
            self.target_loss_count += 1
            self._lost_start_ms = timestamp_ms

        self._prev_state = curr_state

        # Compute spatial tracking error against ground truth
        inst_err: Optional[float] = None
        if gt_point is not None:
            tx = tracking_result.measured_x if tracking_result.measured_x is not None else tracking_result.predicted_x
            ty = tracking_result.measured_y if tracking_result.measured_y is not None else tracking_result.predicted_y
            inst_err = float(math.hypot(tx - gt_point.target_x, ty - gt_point.target_y))
            self.errors_px.append(inst_err)

        # Calculate statistics
        rmse = float(np.sqrt(np.mean(np.square(self.errors_px)))) if self.errors_px else None
        mean_err = float(np.mean(self.errors_px)) if self.errors_px else None
        max_err = float(np.max(self.errors_px)) if self.errors_px else None
        median_err = float(np.median(self.errors_px)) if self.errors_px else None

        lock_retention = (self.frames_tracked / self.total_frames * 100.0) if self.total_frames > 0 else 0.0
        
        avg_lat = float(np.mean(self.frame_latencies_ms)) if self.frame_latencies_ms else 0.0
        fps = (1000.0 / avg_lat) if avg_lat > 0.0 else 0.0
        max_lat = float(np.max(self.frame_latencies_ms)) if self.frame_latencies_ms else 0.0

        mean_reacq = float(np.mean(self.reacquisition_times_ms)) if self.reacquisition_times_ms else None

        return MetricsResult(
            instantaneous_error_px=inst_err,
            rmse_px=rmse,
            mean_error_px=mean_err,
            max_error_px=max_err,
            median_error_px=median_err,
            acquisition_time_ms=self.first_track_timestamp_ms,
            reacquisition_time_ms=mean_reacq,
            lock_retention_percent=lock_retention,
            processing_fps=fps,
            processing_time_ms=processing_time_ms,
            max_processing_time_ms=max_lat,
            frames_processed=self.total_frames,
            frames_lost=self.frames_lost,
            target_loss_count=self.target_loss_count,
        )

    def get_summary(self) -> Dict[str, Any]:
        """Returns final serializable run summary."""
        rmse = float(np.sqrt(np.mean(np.square(self.errors_px)))) if self.errors_px else None
        mean_err = float(np.mean(self.errors_px)) if self.errors_px else None
        std_err = float(np.std(self.errors_px)) if self.errors_px else None
        max_err = float(np.max(self.errors_px)) if self.errors_px else None
        median_err = float(np.median(self.errors_px)) if self.errors_px else None

        latencies = np.array(self.frame_latencies_ms) if self.frame_latencies_ms else np.array([0.0])
        p50 = float(np.percentile(latencies, 50))
        p95 = float(np.percentile(latencies, 95))
        p99 = float(np.percentile(latencies, 99))
        avg_fps = (1000.0 / float(np.mean(latencies))) if np.mean(latencies) > 0 else 0.0

        return {
            "total_frames": self.total_frames,
            "frames_tracked": self.frames_tracked,
            "frames_lost": self.frames_lost,
            "lock_retention_percent": round((self.frames_tracked / self.total_frames * 100.0) if self.total_frames > 0 else 0.0, 2),
            "target_loss_count": self.target_loss_count,
            "acquisition_time_ms": round(self.first_track_timestamp_ms, 2) if self.first_track_timestamp_ms else None,
            "reacquisition_time_ms": round(float(np.mean(self.reacquisition_times_ms)), 2) if self.reacquisition_times_ms else None,
            "rmse_px": round(rmse, 3) if rmse is not None else None,
            "mean_error_px": round(mean_err, 3) if mean_err is not None else None,
            "std_error_px": round(std_err, 3) if std_err is not None else None,
            "median_error_px": round(median_err, 3) if median_err is not None else None,
            "max_error_px": round(max_err, 3) if max_err is not None else None,
            "fps_mean": round(avg_fps, 2),
            "latency_p50_ms": round(p50, 2),
            "latency_p95_ms": round(p95, 2),
            "latency_p99_ms": round(p99, 2),
            "latency_max_ms": round(float(np.max(latencies)), 2),
        }
