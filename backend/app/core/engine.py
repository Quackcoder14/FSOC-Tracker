"""
FSOC Tracking Engine — Top-level execution coordinator.

Manages source lifecycle, tracking pipeline execution, telemetry dispatch,
and experiment report compilation.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, Optional, Union

import cv2

from app.core.interfaces import FrameSource
from app.core.models import Frame, TelemetryPacket
from app.core.pipeline import TrackingPipeline
from app.input.virtual_camera import VirtualCameraSource
from app.input.video_file import VideoFileSource
from app.evaluation.ground_truth import GroundTruthLoader, GroundTruthPoint
from app.evaluation.reports import ReportGenerator

logger = logging.getLogger(__name__)


class Engine:
    """
    Core engine managing pipeline lifecycle and source streaming.

    Public properties
    -----------------
    is_running : bool
    is_paused  : bool
    mode       : str
    """

    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.pipeline = TrackingPipeline(cfg)
        self.report_generator = ReportGenerator()
        self.gt_loader = GroundTruthLoader()

        self.mode: str = "simulation"
        self.source: Optional[FrameSource] = None

        self._running: bool = False
        self._paused: bool = False
        self._run_task: Optional[asyncio.Task] = None
        self._telemetry_callback: Optional[Callable[[dict], Coroutine[Any, Any, None]]] = None

        self._run_id: str = f"run_{int(time.time())}"
        self.include_image_stream: bool = True
        self.jpeg_quality: int = 75

        # Initialize default simulation source
        self._setup_source("simulation")

    # ------------------------------------------------------------------
    # Public properties (avoid leaking _running/_paused to callers)
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    def set_telemetry_callback(self, cb: Callable[[dict], Coroutine[Any, Any, None]]) -> None:
        self._telemetry_callback = cb

    # ------------------------------------------------------------------
    # Source management
    # ------------------------------------------------------------------

    def _setup_source(self, mode: str, video_path: Optional[str] = None, gt_path: Optional[str] = None) -> None:
        self.mode = mode
        if self.source is not None:
            try:
                self.source.stop()
            except Exception:
                pass

        if mode == "simulation":
            self.source = VirtualCameraSource(self.cfg)
        elif mode in ("benchmark", "video"):
            if not video_path:
                raise ValueError(f"Mode '{mode}' requires video_path")
            vp = Path(video_path)
            if not vp.exists():
                raise FileNotFoundError(f"Video file not found: {vp}")
            self.source = VideoFileSource(str(vp))
            if gt_path:
                gtp = Path(gt_path)
                if not gtp.exists():
                    raise FileNotFoundError(f"Ground truth file not found: {gtp}")
                self.gt_loader.load(str(gtp))
        else:
            raise ValueError(f"Unknown mode: {mode!r}")

    def configure_mode(self, mode: str, video_path: Optional[str] = None, gt_path: Optional[str] = None) -> None:
        """
        Switch running mode (simulation or benchmark).

        Transactional: if validation fails, the engine keeps its previous working source.
        Raises ValueError / FileNotFoundError on invalid inputs (caller should handle).
        """
        was_running = self._running
        if was_running:
            self.stop()

        # Attempt to build a candidate source before committing
        prev_source = self.source
        prev_mode   = self.mode
        try:
            self._setup_source(mode, video_path, gt_path)
        except (ValueError, FileNotFoundError):
            # Roll back — restore previous source/mode
            self.source = prev_source
            self.mode   = prev_mode
            raise

        self.pipeline.reset()
        self._run_id = f"{mode}_{int(time.time())}"

        if was_running:
            self.start()

    # ------------------------------------------------------------------
    # Runtime configuration updates (simulation mode only)
    # ------------------------------------------------------------------

    def update_disturbances(self, disturbance_settings: dict) -> None:
        """
        Dynamically update disturbance settings when in simulation mode.

        Routes through VirtualCameraSource.update_disturbances() →
        DisturbanceEngine.update_from_dict() which rebuilds the active
        disturbance module pipeline. No private attributes are accessed here.
        """
        if isinstance(self.source, VirtualCameraSource):
            self.source.update_disturbances(disturbance_settings)
            logger.info("Disturbances updated: %s", list(disturbance_settings.keys()))
        else:
            logger.warning("update_disturbances called but source is not VirtualCameraSource")

    def update_trajectory(self, trajectory_settings: dict) -> None:
        """Dynamically update target trajectory when in simulation mode."""
        if isinstance(self.source, VirtualCameraSource):
            from app.simulation.target import TrajectoryType
            traj_type = TrajectoryType.from_string(trajectory_settings.get("type", "circular"))
            self.source.update_trajectory(trajectory_settings)
            self.pipeline.reset()
            logger.info("Simulation trajectory updated: %s", traj_type.value)
        else:
            logger.warning("update_trajectory called but source is not VirtualCameraSource")

    def update_camera(self, camera_settings: dict) -> None:
        """
        Dynamically update virtual camera parameters (HFOV, VFOV, beacon size).
        Only applies in simulation mode.
        """
        if isinstance(self.source, VirtualCameraSource):
            self.source.update_camera(camera_settings)
            logger.info("Camera settings updated: %s", camera_settings)
        else:
            logger.warning("update_camera called but source is not VirtualCameraSource")

    def configure_simulation_scenario(self, scenario_type: str, params: Optional[dict] = None) -> None:
        """Configure simulation scenario (e.g. 'acceptance', 'circular', 'figure8')."""
        p = dict(params or {})
        p["type"] = scenario_type
        self.update_trajectory(p)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the tracking execution loop."""
        if self._running:
            return

        if self.source is None:
            self._setup_source(self.mode)

        self.source.start()
        self.pipeline.reset()
        self._running = True
        self._paused = False
        self._run_id = f"{self.mode}_{int(time.time())}"

        self._run_task = asyncio.create_task(self._loop())
        logger.info("Engine started in %s mode (run_id: %s)", self.mode, self._run_id)

    def stop(self) -> None:
        """Stop tracking loop and clean up."""
        self._running = False
        self._paused = False
        if self._run_task and not self._run_task.done():
            self._run_task.cancel()
        if self.source is not None:
            try:
                self.source.stop()
            except Exception:
                pass
        logger.info("Engine stopped")

    def pause(self) -> None:
        self._paused = True
        logger.info("Engine paused")

    def resume(self) -> None:
        self._paused = False
        logger.info("Engine resumed")

    def step(self) -> Optional[TelemetryPacket]:
        """Execute exactly one frame step synchronously."""
        if self.source is None:
            return None

        frame = self.source.read()
        if frame is None:
            return None

        # Fetch ground truth if available
        gt_pt: Optional[GroundTruthPoint] = None
        cam = None
        disturbance_context = None
        if isinstance(self.source, VirtualCameraSource):
            cam = self.source.camera
            if self.source.last_target_state is not None:
                ts = self.source.last_target_state
                gt_px, gt_py = cam.world_to_pixel(ts.pan_deg, ts.tilt_deg)
                gt_pt = GroundTruthPoint(
                    frame_index=frame.frame_index,
                    timestamp_ms=frame.timestamp_ms,
                    target_x=gt_px,
                    target_y=gt_py,
                    target_pan_deg=ts.pan_deg,
                    target_tilt_deg=ts.tilt_deg,
                )
            # Get disturbance context for world visualization
            disturbance_context = self.source.get_disturbance_context()
        elif self.mode == "benchmark":
            gt_pt = self.gt_loader.get_for_frame(frame.frame_index)

        telemetry, _, _, _, _ = self.pipeline.process_frame(
            frame=frame,
            gt_point=gt_pt,
            camera=cam,
            disturbance_context=disturbance_context,
        )
        telemetry.mode = self.mode

        return telemetry

    # ------------------------------------------------------------------
    # Main processing loop
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        """Continuous async processing loop."""
        target_fps = float(self.cfg.get("system", {}).get("target_fps", 30.0))
        target_period = 1.0 / max(target_fps, 1.0)

        try:
            while self._running:
                if self._paused:
                    await asyncio.sleep(0.05)
                    continue

                t_start = time.perf_counter()

                frame = self.source.read() if self.source else None
                if frame is None:
                    logger.info("End of frame source reached")
                    self._running = False
                    break

                # Resolve ground truth & camera
                gt_pt: Optional[GroundTruthPoint] = None
                cam = None
                disturbance_context = None
                if isinstance(self.source, VirtualCameraSource):
                    cam = self.source.camera
                    if self.source.last_target_state is not None:
                        ts = self.source.last_target_state
                        gt_px, gt_py = cam.world_to_pixel(ts.pan_deg, ts.tilt_deg)
                        gt_pt = GroundTruthPoint(
                            frame_index=frame.frame_index,
                            timestamp_ms=frame.timestamp_ms,
                            target_x=gt_px,
                            target_y=gt_py,
                            target_pan_deg=ts.pan_deg,
                            target_tilt_deg=ts.tilt_deg,
                        )
                    disturbance_context = self.source.get_disturbance_context()
                elif self.mode == "benchmark":
                    gt_pt = self.gt_loader.get_for_frame(frame.frame_index)

                telemetry, det, track, ctrl, metrics = self.pipeline.process_frame(
                    frame=frame,
                    gt_point=gt_pt,
                    camera=cam,
                    disturbance_context=disturbance_context,
                )

                # Send telemetry via callback if registered
                if self._telemetry_callback is not None:
                    telemetry.mode = self.mode
                    payload = telemetry.to_dict()
                    payload["mode"] = self.mode

                    # Optionally encode frame image as JPEG base64 for web display
                    if self.include_image_stream:
                        success, buf = cv2.imencode(
                            ".jpg",
                            frame.image,
                            [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality],
                        )
                        if success:
                            payload["image_base64"] = base64.b64encode(buf).decode("ascii")

                    try:
                        await self._telemetry_callback(payload)
                    except Exception as e:
                        logger.debug("Failed sending telemetry: %s", e)

                # Frame rate throttling
                t_elapsed = time.perf_counter() - t_start
                sleep_time = target_period - t_elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    await asyncio.sleep(0.001)  # Yield to event loop

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Error in engine loop: %s", e, exc_info=True)
        finally:
            self._running = False
            if self._telemetry_callback is not None:
                status_payload = {
                    "type": "STATUS",
                    "mode": self.mode,
                    "running": False,
                    "paused": False,
                    "completed": True,
                }
                try:
                    await self._telemetry_callback(status_payload)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def generate_report(self, output_dir: Optional[Union[str, Path]] = None) -> Dict[str, Path]:
        """Compile run report from accumulated metrics."""
        out = output_dir or (Path("results") / self._run_id)
        summary = self.pipeline.metrics.get_summary()
        return self.report_generator.generate(
            run_id=self._run_id,
            config=self.cfg,
            metrics_summary=summary,
            output_dir=out,
            mode=self.mode,
            error_series=self.pipeline.metrics.errors_px,
        )
