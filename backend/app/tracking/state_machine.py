"""
Tracking state machine for FSOC beacon tracking.

States:
  SEARCH    → scanning for target; no reliable detection
  ACQUIRE   → candidate found; accumulating consecutive valid frames
  TRACK     → stable lock on target; Kalman active
  PREDICT   → measurement lost; using Kalman prediction only
  REACQUIRE → extended prediction failure; wider search around predicted pos
  LOST      → tracking completely failed; reset to SEARCH

Transitions:
  SEARCH → ACQUIRE       : detection found
  ACQUIRE → SEARCH       : detection lost before accumulation complete
  ACQUIRE → TRACK        : acquisition_frames consecutive valid detections
  TRACK → PREDICT        : measurement lost in one frame
  PREDICT → TRACK        : measurement recovered within max_prediction_frames
  PREDICT → REACQUIRE    : prediction frames exceeded
  REACQUIRE → TRACK      : measurement recovered
  REACQUIRE → LOST       : reacquisition_timeout_ms exceeded
  LOST → SEARCH          : immediate (reset)
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from app.core.models import TrackingState, TrackingResult, DetectionResult
from app.tracking.kalman import KalmanTracker

logger = logging.getLogger(__name__)


class TrackingStateMachine:
    """
    Manages state transitions and drives the Kalman filter.
    """

    def __init__(
        self,
        acquisition_frames: int = 5,
        max_prediction_frames: int = 10,
        reacquisition_timeout_ms: float = 1000.0,
        detection_confidence_threshold: float = 0.60,
        kalman: Optional[KalmanTracker] = None,
        dt: float = 1.0 / 30.0,
    ) -> None:
        self.acquisition_frames    = acquisition_frames
        self.max_prediction_frames = max_prediction_frames
        self.reacquisition_timeout = reacquisition_timeout_ms
        self.confidence_threshold  = detection_confidence_threshold
        self.dt = dt

        self._kalman = kalman or KalmanTracker()
        self._state: TrackingState = TrackingState.SEARCH

        # Counters
        self._acquire_count:   int   = 0
        self._predict_count:   int   = 0
        self._reacquire_start: float = 0.0  # wall-clock ms

        # Metrics
        self._first_track_ts:   Optional[float] = None  # timestamp_ms when TRACK entered first time
        self._track_frames:     int = 0
        self._total_frames:     int = 0
        self._loss_count:       int = 0
        self._loss_start_ts:    Optional[float] = None
        self._reacq_times:      list[float] = []

    # ------------------------------------------------------------------ #
    # Public interface
    # ------------------------------------------------------------------ #

    @property
    def state(self) -> TrackingState:
        return self._state

    @property
    def kalman(self) -> KalmanTracker:
        return self._kalman

    def reset(self) -> None:
        self._state = TrackingState.SEARCH
        self._kalman.reset()
        self._acquire_count  = 0
        self._predict_count  = 0
        self._track_frames   = 0
        self._total_frames   = 0
        self._loss_count     = 0
        self._first_track_ts = None
        self._loss_start_ts  = None
        logger.info("State machine reset → SEARCH")

    def update(
        self,
        detection: DetectionResult,
        timestamp_ms: float,
        dt: Optional[float] = None,
    ) -> TrackingResult:
        """
        Process one detection result and update tracking state.
        Returns a TrackingResult with predicted and measured positions.
        """
        dt = dt if dt is not None else self.dt
        self._total_frames += 1

        valid = detection.detected and detection.confidence >= self.confidence_threshold

        # ── Run Kalman predict step (always when initialized) ──────────
        if self._kalman.initialized:
            pred_x, pred_y = self._kalman.predict(dt)
        else:
            pred_x, pred_y = (
                (detection.x if detection.x else 0.0),
                (detection.y if detection.y else 0.0),
            )

        # ── State transitions ──────────────────────────────────────────
        new_state = self._transition(valid, timestamp_ms)

        # ── Kalman update ──────────────────────────────────────────────
        if valid and new_state in (TrackingState.ACQUIRE, TrackingState.TRACK, TrackingState.REACQUIRE):
            self._kalman.update(detection.x, detection.y)
            # Refresh predicted position after update
            pred_x = float(self._kalman._x[0])
            pred_y = float(self._kalman._x[1])

        # ── Track frame counting ───────────────────────────────────────
        if self._state == TrackingState.TRACK:
            self._track_frames += 1

        vx, vy = self._kalman.velocity if self._kalman.initialized else (0.0, 0.0)
        inn_x, inn_y = self._kalman.innovation if self._kalman.initialized else (0.0, 0.0)

        return TrackingResult(
            predicted_x=pred_x,
            predicted_y=pred_y,
            measured_x=detection.x if valid else None,
            measured_y=detection.y if valid else None,
            velocity_x=vx,
            velocity_y=vy,
            confidence=self._kalman.confidence if self._kalman.initialized else 0.0,
            state=self._state,
            innovation_x=inn_x,
            innovation_y=inn_y,
        )

    # ------------------------------------------------------------------ #
    # State transition logic
    # ------------------------------------------------------------------ #

    def _transition(self, valid: bool, timestamp_ms: float) -> TrackingState:
        prev = self._state

        if self._state == TrackingState.SEARCH:
            if valid:
                self._acquire_count = 1
                if not self._kalman.initialized:
                    pass  # Will be initialized on first update() call
                self._set_state(TrackingState.ACQUIRE, timestamp_ms)

        elif self._state == TrackingState.ACQUIRE:
            if valid:
                self._acquire_count += 1
                if not self._kalman.initialized:
                    pass
                if self._acquire_count >= self.acquisition_frames:
                    self._on_enter_track(timestamp_ms)
                    self._set_state(TrackingState.TRACK, timestamp_ms)
            else:
                self._acquire_count = 0
                self._set_state(TrackingState.SEARCH, timestamp_ms)

        elif self._state == TrackingState.TRACK:
            if not valid:
                self._predict_count = 1
                self._loss_count += 1
                self._loss_start_ts = timestamp_ms
                self._set_state(TrackingState.PREDICT, timestamp_ms)

        elif self._state == TrackingState.PREDICT:
            if valid:
                if self._loss_start_ts is not None:
                    reacq_ms = timestamp_ms - self._loss_start_ts
                    self._reacq_times.append(reacq_ms)
                self._predict_count = 0
                self._set_state(TrackingState.TRACK, timestamp_ms)
            else:
                self._predict_count += 1
                if self._predict_count >= self.max_prediction_frames:
                    self._reacquire_start = timestamp_ms
                    self._set_state(TrackingState.REACQUIRE, timestamp_ms)

        elif self._state == TrackingState.REACQUIRE:
            if valid:
                if self._loss_start_ts is not None:
                    reacq_ms = timestamp_ms - self._loss_start_ts
                    self._reacq_times.append(reacq_ms)
                self._set_state(TrackingState.TRACK, timestamp_ms)
            else:
                elapsed = timestamp_ms - self._reacquire_start
                if elapsed > self.reacquisition_timeout:
                    self._kalman.reset()
                    self._set_state(TrackingState.LOST, timestamp_ms)

        elif self._state == TrackingState.LOST:
            self._set_state(TrackingState.SEARCH, timestamp_ms)

        if prev != self._state:
            logger.info("State: %s → %s @ %.0f ms", prev.value, self._state.value, timestamp_ms)

        return self._state

    def _set_state(self, new_state: TrackingState, timestamp_ms: float) -> None:
        self._state = new_state

    def _on_enter_track(self, timestamp_ms: float) -> None:
        if self._first_track_ts is None:
            self._first_track_ts = timestamp_ms
            logger.info("TARGET_ACQUIRED at %.0f ms (%.2f s)", timestamp_ms, timestamp_ms / 1000)

    # ------------------------------------------------------------------ #
    # Metrics helpers
    # ------------------------------------------------------------------ #

    def acquisition_time_ms(self) -> Optional[float]:
        return self._first_track_ts

    def mean_reacquisition_time_ms(self) -> Optional[float]:
        if not self._reacq_times:
            return None
        return float(sum(self._reacq_times) / len(self._reacq_times))

    def lock_retention_percent(self) -> float:
        if self._total_frames == 0:
            return 0.0
        return 100.0 * self._track_frames / self._total_frames

    def loss_count(self) -> int:
        return self._loss_count
