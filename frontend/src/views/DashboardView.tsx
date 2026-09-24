import React from "react";
import { TelemetryPacket } from "../types/telemetry";
import { TrackingCanvas } from "../canvas/TrackingCanvas";
import { TelemetryChartsGrid } from "../charts/TelemetryCharts";
import { wsService } from "../services/websocket";
import { StatusBadge, trackingStateToVariant } from "../components/ui/StatusBadge";
import { ControlButton } from "../components/ui/ControlButton";
import { SectionHeader } from "../components/ui/SectionHeader";
import { MetricRow } from "../components/ui/MetricRow";
import { FullscreenContainer } from "../components/FullscreenContainer";
import { Play, Square, Pause, SkipForward, Maximize2, Minimize2, Search, RotateCcw } from "lucide-react";

interface DashboardViewProps {
  telemetry: TelemetryPacket | null;
  history: {
    error_x: number[];
    error_y: number[];
    rmse: number[];
    pan_cmd: number[];
    tilt_cmd: number[];
    latency: number[];
  };
  mode: string;
  running: boolean;
  paused: boolean;
  displayFps?: number;
}

const ZOOM_LEVELS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0] as const;

export const DashboardView: React.FC<DashboardViewProps> = ({
  telemetry,
  history,
  running,
  paused,
  displayFps = 20,
}) => {
  const [showDebug, setShowDebug] = React.useState(true);
  const [showVector, setShowVector] = React.useState(true);
  const [zoomLevel, setZoomLevel] = React.useState(2); // index 2 = 1.0 (100%)

  const state = telemetry?.tracking?.state ?? "IDLE";
  const trackVariant = trackingStateToVariant(state);

  const fps = telemetry?.performance?.fps;
  const rmse = telemetry?.performance?.rmse_px;
  const lock = telemetry?.performance?.lock_retention_pct;
  const latency = telemetry?.performance?.latency_ms;
  const confidence = telemetry?.tracking?.confidence;
  const instantErr = telemetry?.performance?.instant_error_px;

  const panCmd = telemetry?.control?.pan_cmd_deg_s;
  const tiltCmd = telemetry?.control?.tilt_cmd_deg_s;
  const camPan = telemetry?.control?.camera_pan_deg;
  const camTilt = telemetry?.control?.camera_tilt_deg;
  const errXDeg = telemetry?.control?.error_x_deg;
  const errYDeg = telemetry?.control?.error_y_deg;

  const frameIndex = telemetry?.frame_index;

  const viewportTelemetry = React.useMemo(() => ({
    trackingState: state,
    errorPx: instantErr ?? 0,
    azError: errXDeg ?? 0,
    elError: errYDeg ?? 0,
  }), [state, instantErr, errXDeg, errYDeg]);

  const zoomIn = () => setZoomLevel(prev => Math.min(prev + 1, ZOOM_LEVELS.length - 1));
  const zoomOut = () => setZoomLevel(prev => Math.max(prev - 1, 0));
  const resetZoom = () => setZoomLevel(2); // 100%

  const currentZoom = ZOOM_LEVELS[zoomLevel];
  const zoomPercent = Math.round(currentZoom * 100);

  return (
    <div className="flex flex-col h-full min-h-0">

      {/* ── MAIN AREA: Viewport + Telemetry Panel ────────────────── */}
      <div className="flex gap-0 flex-1 min-h-0 overflow-hidden">

        {/* ─ Left: Tracking Viewport ─────────────────────────────── */}
        <div className="flex flex-col flex-1 min-w-0 p-4 gap-3 overflow-hidden flex-[2]">

          {/* Viewport header bar */}
          <div className="flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <StatusBadge variant={trackVariant} />
              </div>
              {frameIndex !== undefined && (
                <span className="font-mono text-[11px] text-[#738397] selectable">
                  FRAME{" "}
                  <span className="text-[#AAB7C5]">{String(frameIndex).padStart(5, "0")}</span>
                </span>
              )}
              {fps !== undefined && (
                <span className="font-mono text-[11px] text-[#738397] selectable">
                  <span className="text-[#AAB7C5]">{fps.toFixed(1)}</span> FPS
                </span>
              )}
            </div>

            {/* Transport controls + Fullscreen + Zoom */}
            <div className="flex items-center gap-1.5">
              {!running ? (
                <ControlButton
                  variant="primary"
                  icon={<Play />}
                  onClick={() => wsService.startSimulation()}
                >
                  START SIM
                </ControlButton>
              ) : (
                <ControlButton
                  variant="danger"
                  icon={<Square />}
                  onClick={() => wsService.stop()}
                >
                  STOP
                </ControlButton>
              )}

              {running && !paused ? (
                <ControlButton
                  variant="secondary"
                  icon={<Pause />}
                  onClick={() => wsService.pause()}
                >
                  PAUSE
                </ControlButton>
              ) : running && paused ? (
                <ControlButton
                  variant="primary"
                  icon={<Play />}
                  onClick={() => wsService.resume()}
                >
                  RESUME
                </ControlButton>
              ) : null}

              <ControlButton
                variant="tertiary"
                icon={<SkipForward />}
                onClick={() => wsService.step()}
                title="Step one frame"
              >
                STEP
              </ControlButton>

              <ControlButton
                variant="tertiary"
                size="sm"
                icon={<RotateCcw />}
                onClick={resetZoom}
                title="Reset zoom"
              >
                RESET ZOOM
              </ControlButton>

              {/* Zoom controls */}
              <div className="flex items-center gap-1 bg-[#111A28] rounded border border-[#26364A] px-2 py-1">
                <ControlButton
                  variant="tertiary"
                  size="sm"
                  icon={<Search />}
                  onClick={zoomOut}
                  disabled={zoomLevel === 0}
                  title="Zoom out"
                />
                <span className="font-mono text-[11px] text-[#AAB7C5] selectable min-w-[3.5rem] text-center">
                  {zoomPercent}%
                </span>
                <ControlButton
                  variant="tertiary"
                  size="sm"
                  icon={<Search />}
                  onClick={zoomIn}
                  disabled={zoomLevel === ZOOM_LEVELS.length - 1}
                  title="Zoom in"
                  className="rotate-180"
                />
              </div>
            </div>
          </div>

          {/* Camera POV Viewport with Fullscreen & Zoom */}
          <FullscreenContainer
            title="CAMERA POV"
            subtitle="Optical Observation"
            telemetry={viewportTelemetry}
            className="flex-1 min-h-0"
          >
            <div className="flex-1 min-h-0 w-full h-full flex items-center justify-center bg-[#0B111B] rounded border border-[#1A2839] p-1 overflow-hidden" style={{ transform: `scale(${currentZoom})`, transformOrigin: "center center" }}>
              <TrackingCanvas
                telemetry={telemetry}
                showDebugOverlay={showDebug}
                showErrorVector={showVector}
              />
            </div>
          </FullscreenContainer>

          {/* Visual Overlays Toggle */}
          <div className="flex items-center gap-1.5 pt-1 flex-shrink-0">
            <ControlButton
              variant={showVector ? "secondary" : "tertiary"}
              size="sm"
              onClick={() => setShowVector(!showVector)}
              title="Toggle orthogonal error vector display"
            >
              ERROR VECTOR: {showVector ? "ON" : "OFF"}
            </ControlButton>
            <ControlButton
              variant={showDebug ? "secondary" : "tertiary"}
              size="sm"
              onClick={() => setShowDebug(!showDebug)}
              title="Toggle technical debug HUD and diagnostic labels"
            >
              DEBUG HUD: {showDebug ? "ON" : "OFF"}
            </ControlButton>
          </div>

          {/* Display FPS Info */}
          <div className="flex items-center justify-between pt-1 border-t border-[#1B2839] flex-shrink-0">
            <div className="flex items-center gap-2 text-[10px]">
              <span className="font-sans text-[#738397] uppercase tracking-wide">DISPLAY</span>
              <span className="font-mono text-[#AAB7C5] selectable">{displayFps} FPS</span>
            </div>
            <div className="flex items-center gap-2 text-[10px]">
              <span className="font-sans text-[#738397] uppercase tracking-wide">ENGINE</span>
              {fps !== undefined && (
                <span className="font-mono text-[#AAB7C5] selectable">{fps.toFixed(1)} FPS</span>
              )}
            </div>
          </div>
        </div>

        {/* ─ Right: Telemetry Panel ───────────────────────────────── */}
        <div
          className="flex-shrink-0 flex flex-col gap-3 p-4 border-l border-[#26364A] bg-[#0B111B] overflow-y-auto"
          style={{ width: 280 }}
        >
          {/* TRACKING */}
          <div className="bg-[#111A28] border border-[#26364A] rounded-md p-4 space-y-3">
            <SectionHeader title="TRACKING" />
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-sans text-[12px] text-[#738397]">State</span>
                <StatusBadge variant={trackVariant} className="text-[12px]" />
              </div>
              <MetricRow
                label="Confidence"
                value={confidence !== undefined ? `${(confidence * 100).toFixed(1)}%` : null}
                mono
              />
              <MetricRow
                label="Image Error"
                value={instantErr?.toFixed(2)}
                unit="px"
              />
              <MetricRow
                label="RMSE"
                value={rmse?.toFixed(2)}
                unit="px"
                valueColor={rmse !== undefined && rmse > 10 ? "text-[#D99A24]" : "text-[#E8EDF3]"}
              />
              <MetricRow
                label="Lock Ret."
                value={lock?.toFixed(1)}
                unit="%"
                valueColor={lock !== undefined && lock >= 90 ? "text-[#38A169]" : "text-[#D99A24]"}
              />
            </div>
          </div>

          {/* OPTICAL PAT */}
          <div className="bg-[#111A28] border border-[#26364A] rounded-md p-4 space-y-3">
            <SectionHeader title="OPTICAL PAT" />
            <div className="space-y-2">
              <MetricRow label="PAN"  value={camPan?.toFixed(3)}  unit="°" />
              <MetricRow label="TILT" value={camTilt?.toFixed(3)} unit="°" />
              <div className="border-t border-[#1B2839] pt-2 mt-1" />
              <MetricRow label="Pan Cmd"  value={panCmd?.toFixed(3)}  unit="°/s" />
              <MetricRow label="Tilt Cmd" value={tiltCmd?.toFixed(3)} unit="°/s" />
            </div>
          </div>

          {/* BEAM POINTING */}
          <div className="bg-[#111A28] border border-[#26364A] rounded-md p-4 space-y-3">
            <SectionHeader title="BEAM POINTING" />
            <div className="space-y-2">
              <MetricRow label="Error X" value={telemetry?.control?.error_x_px?.toFixed(2)} unit="px" />
              <MetricRow label="Error Y" value={telemetry?.control?.error_y_px?.toFixed(2)} unit="px" />
              <div className="border-t border-[#1B2839] pt-2 mt-1" />
              <MetricRow label="Angular X" value={errXDeg?.toFixed(4)} unit="°" />
              <MetricRow label="Angular Y" value={errYDeg?.toFixed(4)} unit="°" />
            </div>
          </div>

          {/* PERFORMANCE */}
          <div className="bg-[#111A28] border border-[#26364A] rounded-md p-4 space-y-3">
            <SectionHeader title="PERFORMANCE" />
            <div className="space-y-2">
              <MetricRow
                label="Engine FPS"
                value={fps?.toFixed(1)}
                unit=""
                valueColor={fps !== undefined && fps < 20 ? "text-[#D9534F]" : "text-[#E8EDF3]"}
              />
              <MetricRow
                label="Display FPS"
                value={displayFps}
                unit="FPS"
              />
              <MetricRow
                label="Latency"
                value={latency?.toFixed(1)}
                unit="ms"
              />
            </div>
          </div>

          {/* DETECTION */}
          <div className="bg-[#111A28] border border-[#26364A] rounded-md p-4 space-y-3">
            <SectionHeader title="DETECTION" />
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-sans text-[12px] text-[#738397]">Beacon</span>
                <StatusBadge
                  variant={telemetry?.detection?.detected ? "track" : "idle"}
                  label={telemetry?.detection?.detected ? "DETECTED" : "NONE"}
                  className="text-[11px]"
                />
              </div>
              <MetricRow
                label="Candidates"
                value={telemetry?.detection?.candidate_count ?? 0}
              />
              <MetricRow
                label="Centroid X"
                value={telemetry?.detection?.x?.toFixed(1)}
                unit="px"
              />
              <MetricRow
                label="Centroid Y"
                value={telemetry?.detection?.y?.toFixed(1)}
                unit="px"
              />
            </div>
          </div>
        </div>
      </div>

      {/* ── BOTTOM: Charts ────────────────────────────────────────── */}
      <div className="flex-shrink-0 border-t border-[#26364A] px-4 py-3 bg-[#0B111B] selectable" style={{ height: 200 }}>
        <div className="mb-2">
          <span className="section-label">Error History & Telemetry</span>
        </div>
        <TelemetryChartsGrid history={history} />
      </div>
    </div>
  );
};

export default DashboardView;