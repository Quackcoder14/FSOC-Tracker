import React, { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { wsService } from "./services/websocket";
import { TelemetryPacket } from "./types/telemetry";
import { DashboardView } from "./views/DashboardView";
import { SimulationControlsView } from "./views/SimulationControlsView";
import { BenchmarkView } from "./views/BenchmarkView";
import { ScientificDebugView } from "./views/ScientificDebugView";
import { ReportsView } from "./views/ReportsView";
import { WorldView } from "./worldView/WorldView";
import { SplitView } from "./worldView/SplitView";
import { FullscreenContainer } from "./components/FullscreenContainer";
import { ErrorBoundary } from "./components/ErrorBoundary";
import {
  Radio,
  Sliders,
  Gauge,
  Microscope,
  FileText,
  Target,
  Box,
  Grid,
  Maximize2,
  Minimize2,
} from "lucide-react";
import { BenchmarkStatus } from "./services/websocket";

type TabId = "overview" | "simulation" | "benchmark" | "scientific" | "results";
type ViewMode = "camera_pov" | "world_view" | "split";

interface RunRecord {
  id: string;
  mode: string;
  rmse: number | null;
  lock: number | null;
  fps: number | null;
  latency: number | null;
  status: "pass" | "fail" | "unknown" | "complete";
  timestamp: string;
  framesProcessed?: number;
  framesEvaluated?: number;
}

const HISTORY_MAX = 80;
const DISPLAY_FPS_OPTIONS = [10, 15, 20, 30] as const;
type DisplayFps = typeof DISPLAY_FPS_OPTIONS[number];

type NavItem = {
  id: TabId;
  label: string;
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
};

export const App: React.FC = () => {
  const [connected, setConnected] = useState(false);
  const [telemetry, setTelemetry] = useState<TelemetryPacket | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [mode, setMode] = useState<string>("simulation");
  const [running, setRunning] = useState<boolean>(false);
  const [paused, setPaused] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<ViewMode>("camera_pov");
  const [displayFps, setDisplayFps] = useState<DisplayFps>(20);
  const [runs, setRuns] = useState<RunRecord[]>([]);

  // Use refs for values that change frequently but shouldn't trigger effect re-runs
  const displayFpsRef = useRef(displayFps);
  const lastTelemetryFrameRef = useRef<number>(0);
  const latestStatusRef = useRef<BenchmarkStatus | null>(null);
  const currentRunModeRef = useRef<string | null>(null);
  const lastRunMetricsRef = useRef<BenchmarkStatus | null>(null);
  const historyRef = useRef<{
    error_x: number[];
    error_y: number[];
    rmse: number[];
    pan_cmd: number[];
    tilt_cmd: number[];
    latency: number[];
  }>({
    error_x: [],
    error_y: [],
    rmse: [],
    pan_cmd: [],
    tilt_cmd: [],
    latency: [],
  });

  // Keep refs in sync with state
  displayFpsRef.current = displayFps;

  const [history, setHistory] = useState(historyRef.current);

  // Stable telemetry handler using refs - never recreated
  const onTelemetry = useCallback((packet: TelemetryPacket) => {
    const now = Date.now();
    const frameInterval = 1000 / displayFpsRef.current;
    if (now - lastTelemetryFrameRef.current < frameInterval) return;
    lastTelemetryFrameRef.current = now;

    setTelemetry(packet);

    // Update history via ref first, then sync to state
    const errX = packet.control?.error_x_px ?? 0;
    const errY = packet.control?.error_y_px ?? 0;
    const rmse = packet.performance?.rmse_px ?? 0;
    const panCmd = packet.control?.pan_cmd_deg_s ?? 0;
    const tiltCmd = packet.control?.tilt_cmd_deg_s ?? 0;
    const lat = packet.performance?.latency_ms ?? 0;

    const h = historyRef.current;
    historyRef.current = {
      error_x: [...h.error_x.slice(-(HISTORY_MAX - 1)), errX],
      error_y: [...h.error_y.slice(-(HISTORY_MAX - 1)), errY],
      rmse: [...h.rmse.slice(-(HISTORY_MAX - 1)), rmse],
      pan_cmd: [...h.pan_cmd.slice(-(HISTORY_MAX - 1)), panCmd],
      tilt_cmd: [...h.tilt_cmd.slice(-(HISTORY_MAX - 1)), tiltCmd],
      latency: [...h.latency.slice(-(HISTORY_MAX - 1)), lat],
    };
    setHistory({ ...historyRef.current });
  }, []);

  // Connect WebSocket ONCE on mount - empty dependency array
  useEffect(() => {
    wsService.connect();
    const unsubConn = wsService.onConnectionChange(setConnected);
    const unsubStatus = wsService.onStatus((status) => {
      if (status.mode) setMode(status.mode);
      if (status.running !== undefined) setRunning(status.running);
      if (status.paused !== undefined) setPaused(status.paused);
    });
    const unsubTelem = wsService.onTelemetry(onTelemetry);
    return () => {
      unsubConn();
      unsubStatus();
      unsubTelem();
      // Note: wsService.disconnect() intentionally NOT called here
      // to prevent reconnection storms from StrictMode or re-renders.
      // The service manages its own lifecycle and reconnection logic.
    };
  }, [onTelemetry]); // onTelemetry is stable (empty deps), so this runs once

  // Track run completions globally (always active regardless of tab)
  useEffect(() => {
    const unsubBenchmark = wsService.onBenchmarkStatus((status) => {
      console.log("[App] Benchmark status:", status);
      latestStatusRef.current = status;

      if (status.state === "running") {
        // Store metrics from running state
        lastRunMetricsRef.current = status;
      } else if (status.state === "completed") {
        // Use stored metrics from running state
        const snap = lastRunMetricsRef.current || latestStatusRef.current;
        const rmse = snap?.currentRmse ?? null;
        const lock = snap?.currentLockRetention ?? null;
        const fps = snap?.currentFps ?? null;
        const latency = snap?.currentLatency ?? null;

        const passed =
          rmse !== null && rmse <= 10.0 &&
          lock !== null && lock >= 90.0 &&
          fps !== null && fps >= 20.0 &&
          latency !== null && latency <= 50.0;

        const mode = currentRunModeRef.current || "benchmark";
        console.log("[App] Creating run record:", { mode, rmse, lock, fps, latency, framesProcessed: snap?.framesProcessed });
        const newRun: RunRecord = {
          id: `${mode === "simulation" ? "sim" : "bm"}_${Date.now()}`,
          mode,
          rmse,
          lock,
          fps,
          latency,
          status: rmse === null && lock === null ? "unknown" : mode === "benchmark" ? (passed ? "pass" : "fail") : "complete",
          timestamp: new Date().toLocaleString(),
          framesProcessed: snap?.framesProcessed,
          framesEvaluated: snap?.framesEvaluated,
        };
        setRuns((prev) => {
          console.log("[App] Adding run to list. Total runs:", prev.length + 1);
          return [newRun, ...prev];
        });
        currentRunModeRef.current = null;
        lastRunMetricsRef.current = null;
      }
    });

    const unsubCommand = wsService.onCommandResult((result) => {
      console.log("[App] Command result:", result);
      if (result.type === "COMMAND_APPLIED") {
        if (result.command === "START_SIMULATION") {
          currentRunModeRef.current = "simulation";
          console.log("[App] Set mode to simulation");
        } else if (result.command === "START_BENCHMARK") {
          currentRunModeRef.current = "benchmark";
          console.log("[App] Set mode to benchmark");
        }
      }
    });

    return () => {
      unsubBenchmark();
      unsubCommand();
    };
  }, []);

  const navItems: NavItem[] = useMemo(() => [
    { id: "overview",    label: "Overview",      icon: Radio },
    { id: "simulation",  label: "Simulation",    icon: Target },
    { id: "benchmark",   label: "Benchmark",     icon: Gauge },
    { id: "scientific",  label: "Scientific",    icon: Microscope },
    { id: "results",     label: "Results",       icon: FileText },
  ], []);

  const state = telemetry?.tracking?.state ?? null;
  const fps = telemetry?.performance?.fps;
  const connectedColor = connected ? "#38A169" : "#D9534F";
  const connectedLabel = connected ? "ENGINE CONNECTED" : "ENGINE OFFLINE";
  const modeLabel = mode?.toUpperCase() ?? "SIMULATION";

  const trackingState = telemetry?.tracking?.state;
  const errorPx = telemetry?.performance?.instant_error_px ?? 0;
  const azError = telemetry?.control?.error_x_deg ?? 0;
  const elError = telemetry?.control?.error_y_deg ?? 0;

  const viewportTelemetry = useMemo(() => ({
    trackingState,
    errorPx,
    azError,
    elError,
  }), [trackingState, errorPx, azError, elError]);

  return (
    <ErrorBoundary>
      <div className="flex flex-col h-full bg-[#070B12] text-[#E8EDF3] font-sans overflow-hidden">
        {/* ─── TOP HEADER ─────────────────────────────────────────────── */}
        <header
          className="flex-shrink-0 flex items-center justify-between px-4 border-b border-[#26364A] bg-[#0B111B]"
          style={{ height: 56 }}
        >
          {/* Left: Identity */}
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-8 h-8 rounded border border-[#26364A] bg-[#111A28] flex-shrink-0">
              <Sliders className="w-4 h-4 text-[#F28C28]" />
            </div>
            <div>
              <div className="font-sans font-semibold text-[14px] text-[#E8EDF3] leading-none tracking-wide">
                FSOC TRACKER
              </div>
              <div className="font-sans text-[10px] text-[#738397] leading-none mt-0.5 tracking-wide uppercase">
                Coarse Alignment & Virtual PAT
              </div>
            </div>
          </div>

          {/* Center: Mode + State */}
          <div className="hidden md:flex items-center gap-6">
            <div className="flex items-center gap-2">
              <span className="font-sans text-[11px] text-[#738397] uppercase tracking-wide">Mode</span>
              <span className="font-mono text-[11px] text-[#F28C28] font-medium">{modeLabel}</span>
            </div>
            {state && (
              <div className="flex items-center gap-1.5">
                <span
                  className="status-dot"
                  style={{
                    backgroundColor:
                      state === "TRACK" ? "#38A169" :
                      state === "ACQUIRE" ? "#D99A24" :
                      state === "LOST" ? "#D9534F" :
                      (state === "PREDICT" || state === "REACQUIRE") ? "#4B93C3" :
                      "#738397",
                  }}
                />
                <span className="font-sans font-medium text-[11px] text-[#AAB7C5]">{state}</span>
              </div>
            )}
            {fps !== undefined && (
              <span className="font-mono text-[11px] text-[#738397]">
                <span className="text-[#AAB7C5]">{fps.toFixed(1)}</span> FPS
              </span>
            )}
          </div>

          {/* Right: Connection + View Mode */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span
                className="status-dot"
                style={{ backgroundColor: connectedColor }}
              />
              <span className="font-sans text-[11px] text-[#AAB7C5]">{connectedLabel}</span>
            </div>
            <div className="w-px h-4 bg-[#26364A]" />
            {/* View Mode Selector */}
            <div className="flex items-center gap-2">
              <span className="font-sans text-[10px] text-[#738397] uppercase tracking-wide">VIEW</span>
              <div className="flex items-center gap-1 bg-[#111A28] rounded border border-[#26364A] p-1">
                <button
                  onClick={() => setViewMode("camera_pov")}
                  className={`px-2.5 py-1 rounded text-[10px] font-mono transition-colors flex items-center gap-1 ${
                    viewMode === "camera_pov"
                      ? "bg-[#1F78B4] text-[#E8EDF3]"
                      : "text-[#738397] hover:text-[#AAB7C5]"
                  }`}
                  title="Camera POV - Optical observation"
                >
                  <Box className="w-3.5 h-3.5" />
                  POV
                </button>
                <button
                  onClick={() => setViewMode("world_view")}
                  className={`px-2.5 py-1 rounded text-[10px] font-mono transition-colors flex items-center gap-1 ${
                    viewMode === "world_view"
                      ? "bg-[#1F78B4] text-[#E8EDF3]"
                      : "text-[#738397] hover:text-[#AAB7C5]"
                  }`}
                  title="World View - External simulation geometry"
                >
                  <Box className="w-3.5 h-3.5" />
                  WORLD
                </button>
                <button
                  onClick={() => setViewMode("split")}
                  className={`px-2.5 py-1 rounded text-[10px] font-mono transition-colors flex items-center gap-1 ${
                    viewMode === "split"
                      ? "bg-[#1F78B4] text-[#E8EDF3]"
                      : "text-[#738397] hover:text-[#AAB7C5]"
                  }`}
                  title="Split View - Camera POV + World View"
                >
                  <Grid className="w-3.5 h-3.5" />
                  SPLIT
                </button>
              </div>
            </div>
            <div className="w-px h-4 bg-[#26364A]" />
            {/* Display FPS Control */}
            <div className="flex items-center gap-2">
              <span className="font-sans text-[10px] text-[#738397] uppercase tracking-wide">DISPLAY</span>
              <select
                value={displayFps}
                onChange={(e) => setDisplayFps(Number(e.target.value) as DisplayFps)}
                className="px-2 py-1 rounded bg-[#111A28] border border-[#26364A] text-[#E8EDF3] font-mono text-[10px] focus:border-[#1F78B4] focus:outline-none appearance-none"
                aria-label="Display telemetry rate"
              >
                {DISPLAY_FPS_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>{opt} FPS</option>
                ))}
              </select>
            </div>
          </div>
        </header>

        {/* ─── BODY: SIDEBAR + WORKSPACE ──────────────────────────────── */}
        <div className="flex flex-1 min-h-0">

          {/* ── SIDEBAR ─────────────────────────────────────────────── */}
          <nav
            className="flex-shrink-0 flex flex-col bg-[#0B111B] border-r border-[#26364A]"
            style={{ width: 210 }}
            aria-label="Main navigation"
          >
            <div className="flex-1 py-3 overflow-y-auto">
              {/* Main nav group */}
              <div className="px-3 mb-1">
                <span className="section-label">Navigation</span>
              </div>
              <ul className="space-y-0.5 px-2" role="list">
                {navItems.map(({ id, label, icon: Icon }) => {
                  const active = activeTab === id;
                  return (
                    <li key={id}>
                      <button
                        onClick={() => setActiveTab(id)}
                        className={`
                          w-full flex items-center gap-2.5 px-3 py-2 rounded text-left
                          transition-colors duration-150 relative
                          font-sans font-medium text-[12px] tracking-wide
                          focus-visible:outline-2 focus-visible:outline-[#1F78B4]
                          ${active
                            ? "bg-[#111A28] text-[#E8EDF3] border border-[#26364A]"
                            : "text-[#738397] hover:text-[#AAB7C5] hover:bg-[#0f1926] border border-transparent"
                          }
                        `}
                        aria-current={active ? "page" : undefined}
                      >
                        {/* Active left indicator */}
                        {active && (
                          <span
                            className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r"
                            style={{ backgroundColor: "#F28C28" }}
                            aria-hidden="true"
                          />
                        )}
                        <Icon
                          className="w-4 h-4 flex-shrink-0"
                          style={{ color: active ? "#F28C28" : undefined }}
                        />
                        {label}
                      </button>
                    </li>
                  );
                })}
              </ul>

              {/* Separator */}
              <div className="mx-3 my-3 border-t border-[#26364A]" />

            {/* Sidebar bottom: build info */}
            <div className="flex-shrink-0 px-3 py-3 border-t border-[#26364A]">
              <div className="font-sans text-[10px] text-[#738397] space-y-0.5">
                <div className="font-medium text-[#AAB7C5]">BUILD 0.4.2</div>
                <div>LOCAL / OFFLINE</div>
              </div>
            </div>
          </div>
          </nav>

          {/* ── WORKSPACE ───────────────────────────────────────────── */}
          <main
            className="flex-1 min-w-0 h-full overflow-hidden bg-[#070B12]"
            id="main-workspace"
            role="main"
          >
            {/* All view components stay mounted to prevent blank screen on switch */}
            <div className="h-full w-full relative" style={{ contain: "layout style" }}>
              {/* CAMERA POV - always mounted, conditionally visible */}
              <div className={`h-full w-full min-h-0 overflow-hidden ${viewMode === "camera_pov" ? "flex flex-col" : "hidden"}`}>
                {activeTab === "overview" && (
                  <DashboardView
                    telemetry={telemetry}
                    history={history}
                    mode={mode}
                    running={running}
                    paused={paused}
                  />
                )}
                {activeTab === "simulation" && (
                  <SimulationControlsView telemetry={telemetry} />
                )}
                {activeTab === "benchmark" && (
                  <BenchmarkView
                    telemetry={telemetry}
                    onNavigateToResults={() => setActiveTab("results")}
                  />
                )}
                {activeTab === "scientific" && (
                  <ScientificDebugView telemetry={telemetry} />
                )}
                {activeTab === "results" && (
                  <ReportsView runs={runs} setRuns={setRuns} />
                )}
              </div>

              {/* WORLD VIEW - always mounted, conditionally visible */}
              <div className={`absolute inset-0 ${viewMode === "world_view" ? "block" : "hidden"}`}>
                <FullscreenContainer
                  title="WORLD VIEW"
                  subtitle="External Simulation Geometry"
                  telemetry={viewportTelemetry}
                  className="h-full"
                >
                  <WorldView telemetry={telemetry} className="h-full" />
                </FullscreenContainer>
              </div>

              {/* SPLIT VIEW - always mounted, conditionally visible */}
              <div className={`absolute inset-0 ${viewMode === "split" ? "block" : "hidden"}`}>
                <FullscreenContainer
                  title="SPLIT VIEW"
                  subtitle="Camera POV + World View"
                  telemetry={viewportTelemetry}
                  className="h-full"
                >
                  <SplitView telemetry={telemetry} />
                </FullscreenContainer>
              </div>
            </div>
          </main>
        </div>

        {/* ─── BOTTOM STATUS BAR ──────────────────────────────────────── */}
        <footer
          className="flex-shrink-0 flex items-center justify-between px-4 border-t border-[#26364A] bg-[#0B111B]"
          style={{ height: 28 }}
        >
          <div className="flex items-center gap-4 font-sans text-[10px] text-[#738397]">
            <span className="flex items-center gap-1.5">
              <span
                className="status-dot"
                style={{ backgroundColor: connected ? "#38A169" : "#D9534F", width: 5, height: 5 }}
              />
              {connected ? "ENGINE CONNECTED" : "ENGINE OFFLINE"}
            </span>
            <span className="text-[#1B2839]">|</span>
            <span>LOCAL MODE</span>
            <span className="text-[#1B2839]">|</span>
            <span>
              <span className="text-[#AAB7C5] font-medium">SOURCE</span>{" "}
              {telemetry ? "ACTIVE" : "IDLE"}
            </span>
            <span className="text-[#1B2839]">|</span>
            <span className="font-sans text-[10px] text-[#738397]">DISPLAY</span>
            <span className="font-mono text-[10px] text-[#AAB7C5]">{displayFps} FPS</span>
            <span className="text-[#1B2839]">|</span>
            <span className="font-sans text-[10px] text-[#738397]">ENGINE</span>
            {fps !== undefined && (
              <>
                <span className="text-[#1B2839]">|</span>
                <span className="font-mono text-[10px] text-[#AAB7C5]">{fps.toFixed(1)}</span>
                <span className="font-sans text-[10px] text-[#738397]">FPS</span>
              </>
            )}
          </div>
          <div className="flex items-center gap-4 font-sans text-[10px] text-[#738397]">
            <span>BUILD 0.4.2</span>
            <span className="text-[#1B2839]">|</span>
            <span>FSOC TRACKER</span>
          </div>
        </footer>
      </div>
    </ErrorBoundary>
  );
};

export default App;