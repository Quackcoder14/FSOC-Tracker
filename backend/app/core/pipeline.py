"""
Common Tracking Pipeline for FSOC beam coarse alignment.

Glues Preprocessing → Classical Detection → AI Validation → Kalman / State Machine → Control → Metrics.
Used identically across Simulation, Benchmark, and Live Video modes.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any, Dict, Optional, Tuple

from app.core.models import (
    ControlResult,
    DetectionResult,
    Frame,
    MetricsResult,
    TelemetryPacket,
    TrackingResult,
    TrackingState,
    WorldState,
)
from app.detection.candidate_detector import CandidateDetector
from app.detection.ai_validator import AIValidator
from app.tracking.kalman import KalmanTracker
from app.tracking.state_machine import TrackingStateMachine
from app.control.camera_controller import CameraController
from app.evaluation.metrics import MetricsAccumulator
from app.evaluation.ground_truth import GroundTruthPoint
from app.simulation.camera import VirtualCamera

logger = logging.getLogger(__name__)


class TrackingPipeline:
    """
    Unified tracking pipeline executed per frame.
    """

    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        target_fps = float(cfg.get("system", {}).get("target_fps", 30.0))
        self.default_dt = 1.0 / max(target_fps, 1.0)

        # 1. Classical Candidate Detector
        beacon_cfg = cfg.get("beacon", {})
        self.detector = CandidateDetector(
            min_size_px=int(beacon_cfg.get("min_size_px", 3)),
            max_size_px=int(beacon_cfg.get("max_size_px", 40)),
            target_size_px=int(beacon_cfg.get("size_px", 10)),
        )

        # 2. AI Validator
        ai_cfg = cfg.get("ai", {})
        self.ai_validator = AIValidator(
            model_path=ai_cfg.get("model_path", "models/beacon_validator.onnx"),
            enabled=bool(ai_cfg.get("enabled", True)),
            confidence_threshold=float(ai_cfg.get("confidence_threshold", 0.7)),
            invoke_on_ambiguous=bool(ai_cfg.get("invoke_on_ambiguous", True)),
            max_candidates_for_ai=int(ai_cfg.get("max_candidates_for_ai", 5)),
        )

        # 3. Tracking State Machine (Kalman filter inside)
        track_cfg = cfg.get("tracking", {})
        kalman_cfg = cfg.get("kalman", {})
        kalman_tracker = KalmanTracker(
            process_noise=float(kalman_cfg.get("process_noise", 800.0)),
            measurement_noise=float(kalman_cfg.get("measurement_noise", 1.5)),
            initial_covariance=float(kalman_cfg.get("initial_covariance", 50.0)),
            dt=self.default_dt,
        )
        self.state_machine = TrackingStateMachine(
            kalman=kalman_tracker,
            acquisition_frames=int(track_cfg.get("acquisition_frames", 3)),
            max_prediction_frames=int(track_cfg.get("max_prediction_frames", 12)),
            reacquisition_timeout_ms=float(track_cfg.get("reacquisition_timeout_ms", 1000.0)),
            detection_confidence_threshold=float(track_cfg.get("detection_confidence_threshold", 0.50)),
            dt=self.default_dt,
        )

        # 4. Camera Pointing Controller (PID)
        self.controller = CameraController(cfg)

        # 5. Metrics Engine
        self.metrics = MetricsAccumulator()

    def reset(self) -> None:
        """Reset internal states across all pipeline stages."""
        self.state_machine.reset()
        self.controller.reset()
        self.metrics.reset()

    def process_frame(
        self,
        frame: Frame,
        gt_point: Optional[GroundTruthPoint] = None,
        camera: Optional[VirtualCamera] = None,
        disturbance_context: Optional[dict] = None,
    ) -> Tuple[TelemetryPacket, DetectionResult, TrackingResult, ControlResult, MetricsResult]:
        """
        Process a single frame through the complete FSOC alignment pipeline.
        """
        t0 = time.perf_counter()
        dt = (1.0 / frame.fps) if frame.fps > 0 else self.default_dt

        # ── 1. Kalman prediction for spatial gating (non-mutating peek) ──
        pred_x: Optional[float] = None
        pred_y: Optional[float] = None
        if self.state_machine.kalman.initialized:
            pred_x, pred_y = self.state_machine.kalman.peek_predict(dt=dt)

        # ── 2. Classical Beacon Candidate Detection ──
        det_result = self.detector.detect(frame.image, pred_x, pred_y)

        # ── 3. AI Validation (if candidates found) ──
        if det_result.detected and self.ai_validator.available and det_result.candidates:
            validated = self.ai_validator.validate_candidates(frame.image, det_result.candidates)
            det_result.candidates = validated
            if validated:
                validated.sort(key=lambda c: c.final_score, reverse=True)
                best = validated[0]
                det_result.x = best.x
                det_result.y = best.y
                det_result.confidence = best.final_score

        # ── 4. State Machine & Kalman Update ──
        tracking_result = self.state_machine.update(
            detection=det_result,
            timestamp_ms=frame.timestamp_ms,
            dt=dt,
        )

        # ── 5. Control Computation (PID) ──
        target_ctrl_x: Optional[float] = None
        target_ctrl_y: Optional[float] = None

        if tracking_result.state in (TrackingState.TRACK, TrackingState.ACQUIRE):
            target_ctrl_x = tracking_result.measured_x if tracking_result.measured_x is not None else tracking_result.predicted_x
            target_ctrl_y = tracking_result.measured_y if tracking_result.measured_y is not None else tracking_result.predicted_y
        elif tracking_result.state in (TrackingState.PREDICT, TrackingState.REACQUIRE):
            target_ctrl_x = tracking_result.predicted_x
            target_ctrl_y = tracking_result.predicted_y

        control_result = self.controller.update(
            target_x=target_ctrl_x,
            target_y=target_ctrl_y,
            dt=dt,
            camera=camera,
        )

        # ── 6. Metrics & Profiling ──
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        metrics_result = self.metrics.update(
            frame_index=frame.frame_index,
            timestamp_ms=frame.timestamp_ms,
            tracking_result=tracking_result,
            detected=det_result.detected,
            gt_point=gt_point,
            processing_time_ms=elapsed_ms,
        )

        # ── 7. Telemetry Packet Serialization ──
        telemetry = self._build_telemetry(
            frame=frame,
            det=det_result,
            track=tracking_result,
            ctrl=control_result,
            metrics=metrics_result,
            gt_point=gt_point,
            camera=camera,
            disturbance_context=disturbance_context,
        )

        return telemetry, det_result, tracking_result, control_result, metrics_result

    def _build_telemetry(
        self,
        frame: Frame,
        det: DetectionResult,
        track: TrackingResult,
        ctrl: ControlResult,
        metrics: MetricsResult,
        gt_point: Optional[GroundTruthPoint],
        camera: Optional[VirtualCamera],
        disturbance_context: Optional[dict] = None,
    ) -> TelemetryPacket:
        det_payload = {
            "detected": det.detected,
            "x": round(det.x, 2) if det.x is not None else None,
            "y": round(det.y, 2) if det.y is not None else None,
            "confidence": round(det.confidence, 3),
            "candidate_count": det.candidate_count,
            "candidates": [
                {
                    "x": round(c.x, 2),
                    "y": round(c.y, 2),
                    "area": round(c.area, 1),
                    "brightness": round(c.brightness, 1),
                    "cv_score": round(c.cv_score, 3),
                    "ai_score": round(c.ai_score, 3) if c.ai_score is not None else None,
                    "final_score": round(c.final_score, 3),
                }
                for c in det.candidates[:5]
            ],
        }

        track_payload = {
            "state": track.state.value,
            "predicted_x": round(track.predicted_x, 2),
            "predicted_y": round(track.predicted_y, 2),
            "measured_x": round(track.measured_x, 2) if track.measured_x is not None else None,
            "measured_y": round(track.measured_y, 2) if track.measured_y is not None else None,
            "velocity_x": round(track.velocity_x, 2),
            "velocity_y": round(track.velocity_y, 2),
            "confidence": round(track.confidence, 3),
        }

        pid_diag = self.controller.get_diagnostics()
        ctrl_payload = {
            "error_x_px": round(ctrl.error_x_px, 2),
            "error_y_px": round(ctrl.error_y_px, 2),
            "error_x_deg": round(ctrl.error_x_deg, 4),
            "error_y_deg": round(ctrl.error_y_deg, 4),
            "pan_cmd_deg_s": round(ctrl.pan_command_deg_s, 3),
            "tilt_cmd_deg_s": round(ctrl.tilt_command_deg_s, 3),
            "camera_pan_deg": round(camera.state.pan_deg, 4) if camera else 0.0,
            "camera_tilt_deg": round(camera.state.tilt_deg, 4) if camera else 0.0,
            "pid_pan": pid_diag.get("pan"),
            "pid_tilt": pid_diag.get("tilt"),
        }

        perf_payload = {
            "fps": round(metrics.processing_fps, 1),
            "latency_ms": round(metrics.processing_time_ms, 2),
            "lock_retention_pct": round(metrics.lock_retention_percent, 1),
            "rmse_px": round(metrics.rmse_px, 2) if metrics.rmse_px is not None else None,
            "instant_error_px": round(metrics.instantaneous_error_px, 2) if metrics.instantaneous_error_px is not None else None,
        }

        gt_payload = None
        if gt_point is not None:
            gt_payload = {
                "target_x": round(gt_point.target_x, 2),
                "target_y": round(gt_point.target_y, 2),
                "target_pan_deg": round(gt_point.target_pan_deg, 4) if gt_point.target_pan_deg is not None else None,
                "target_tilt_deg": round(gt_point.target_tilt_deg, 4) if gt_point.target_tilt_deg is not None else None,
            }

        # ── World State for 3D Visualization ───────────────────────────
        world_payload = None
        if camera is not None and gt_point is not None and gt_point.target_pan_deg is not None and gt_point.target_tilt_deg is not None:
            world_payload = _build_world_state(
                camera=camera,
                target_pan_deg=gt_point.target_pan_deg,
                target_tilt_deg=gt_point.target_tilt_deg,
                disturbance_context=disturbance_context,
            )

        return TelemetryPacket(
            frame_index=frame.frame_index,
            timestamp_ms=frame.timestamp_ms,
            detection=det_payload,
            tracking=track_payload,
            control=ctrl_payload,
            performance=perf_payload,
            ground_truth=gt_payload,
            world=world_payload,
        )


def _build_world_state(
    camera: VirtualCamera,
    target_pan_deg: float,
    target_tilt_deg: float,
    target_distance: float = 10.0,
    disturbance_context: Optional[dict] = None,
) -> dict:
    """
    Build world state for 3D visualization.

    Coordinate system (right-handed, meters):
    - Camera at origin (0, 0, 0)
    - +X = right, +Y = up, +Z = forward (along initial boresight)
    - Target at distance along its angular direction
    """
    # Camera orientation (pan = rotation around Y, tilt = rotation around X)
    pan_rad = math.radians(camera.state.pan_deg)
    tilt_rad = math.radians(camera.state.tilt_deg)

    # Boresight direction vector (camera optical axis)
    # Camera pan: positive = camera rotates right (boresight points left in world)
    # Camera tilt: positive = camera rotates up (boresight points down in world)
    # So boresight in world = (-sin(pan), -sin(tilt), cos(pan)*cos(tilt)) approximately
    # But let's use the proper rotation matrix
    # R = R_y(pan) * R_x(tilt) applied to (0, 0, 1)
    cos_pan = math.cos(pan_rad)
    sin_pan = math.sin(pan_rad)
    cos_tilt = math.cos(tilt_rad)
    sin_tilt = math.sin(tilt_rad)

    # Boresight direction in world coordinates
    boresight_x = sin_pan * cos_tilt
    boresight_y = sin_tilt
    boresight_z = cos_pan * cos_tilt

    # Target direction in world coordinates
    target_pan_rad = math.radians(target_pan_deg)
    target_tilt_rad = math.radians(target_tilt_deg)
    cos_tpan = math.cos(target_pan_rad)
    sin_tpan = math.sin(target_pan_rad)
    cos_tilt_t = math.cos(target_tilt_rad)
    sin_tilt_t = math.sin(target_tilt_rad)

    target_x = target_distance * sin_tpan * cos_tilt_t
    target_y = target_distance * sin_tilt_t
    target_z = target_distance * cos_tpan * cos_tilt_t

    # Apply platform motion and camera jitter from disturbance context
    # These are pixel offsets that need to be converted to world position
    cam_pos_x = 0.0
    cam_pos_y = 0.0
    cam_pos_z = 0.0

    if disturbance_context:
        # Platform motion (smoothed camera position offset in pixels)
        # Convert pixel offset to world offset at target distance
        # 1 pixel = 1/px_per_deg degrees, then degrees to radians, then to world units
        px_per_deg_x = camera._px_per_deg_x
        px_per_deg_y = camera._px_per_deg_y
        
        if "platform_motion_x" in disturbance_context:
            px_offset = disturbance_context["platform_motion_x"]
            deg_offset = px_offset / px_per_deg_x
            cam_pos_x = target_distance * math.tan(math.radians(deg_offset))
        
        if "platform_motion_y" in disturbance_context:
            px_offset = disturbance_context["platform_motion_y"]
            deg_offset = px_offset / px_per_deg_y
            cam_pos_y = target_distance * math.tan(math.radians(deg_offset))
        
        # Camera jitter (high-frequency camera orientation jitter)
        # This affects the boresight direction, not position
        # The jitter is already baked into the image, so we don't modify world position here
        # but we could add it as an additional boresight perturbation if needed

    return {
        "target_position": [round(target_x, 4), round(target_y, 4), round(target_z, 4)],
        "camera_position": [round(cam_pos_x, 4), round(cam_pos_y, 4), round(cam_pos_z, 4)],
        "camera_pan_deg": round(camera.state.pan_deg, 4),
        "camera_tilt_deg": round(camera.state.tilt_deg, 4),
        "boresight_direction": [round(boresight_x, 4), round(boresight_y, 4), round(boresight_z, 4)],
        "hfov_deg": round(camera.hfov, 2),
        "vfov_deg": round(camera.vfov, 2),
        "target_distance": round(target_distance, 2),
    }
