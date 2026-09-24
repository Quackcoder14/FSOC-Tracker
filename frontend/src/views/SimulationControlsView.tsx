import React, { useState, useEffect, useCallback, useMemo } from "react";
import { wsService } from "../services/websocket";
import { TelemetryPacket, CommandResult } from "../types/telemetry";
import { ControlButton } from "../components/ui/ControlButton";
import { SectionHeader, PageHeader } from "../components/ui/SectionHeader";
import { PanelSection } from "../components/ui/PanelSection";
import { TrackingCanvas } from "../canvas/TrackingCanvas";
import { FullscreenContainer } from "../components/FullscreenContainer";
import { ChevronDown, RotateCcw, Play, CheckCircle2, AlertCircle, Maximize2, Minimize2, Search } from "lucide-react";

interface SimulationControlsViewProps {
  telemetry?: TelemetryPacket | null;
}

type AtmosphereType = "clear" | "haze" | "fog" | "rain";
type TrajectoryType = "acceptance" | "figure8" | "lissajous" | "linear" | "random" | "circular";

interface DisturbanceState {
  gaussian: { enabled: boolean; sigma: number };
  saltPepper: { enabled: boolean; prob: number };
  blur: { enabled: boolean; kernel: number };
  jitter: { enabled: boolean; maxPx: number };
  platformMotion: { enabled: boolean; maxPx: number };
  lowLight: { enabled: boolean };
  haze: { enabled: boolean; level: number };
}

const TRAJECTORIES: { id: TrajectoryType; label: string }[] = [
  { id: "acceptance", label: "Acceptance Test (Off-Axis)" },
  { id: "figure8",    label: "Figure-8 (2.0°/s)" },
  { id: "circular",   label: "Circular (1.5°/s)" },
  { id: "linear",     label: "Linear Drift" },
  { id: "random",     label: "Random Walk" },
  { id: "lissajous",  label: "Lissajous Complex" },
];

const ZOOM_LEVELS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0] as const;

export const SimulationControlsView: React.FC<SimulationControlsViewProps> = ({ telemetry }) => {
  const [atmosphere, setAtmosphere] = useState<AtmosphereType>("clear");
  const [trajectory, setTrajectory] = useState<TrajectoryType>("acceptance");
  const [speed, setSpeed] = useState(2.0);
  const [beaconSize, setBeaconSize] = useState(10);
  const [hfov, setHfov] = useState(4.0);
  const [vfov, setVfov] = useState(3.0);
  const [zoomLevel, setZoomLevel] = useState(2); // index 2 = 1.0 (100%)

  const [lastAck, setLastAck] = useState<CommandResult | null>(null);
  const [applying, setApplying] = useState(false);

  const [disturbances, setDisturbances] = useState<DisturbanceState>({
    gaussian:       { enabled: false, sigma: 10 },
    saltPepper:     { enabled: false, prob: 0.01 },
    blur:           { enabled: false, kernel: 3 },
    jitter:         { enabled: false, maxPx: 5 },
    platformMotion: { enabled: false, maxPx: 3 },
    lowLight:       { enabled: false },
    haze:           { enabled: false, level: 0.35 },
  });

  const zoomIn = () => setZoomLevel(prev => Math.min(prev + 1, ZOOM_LEVELS.length - 1));
  const zoomOut = () => setZoomLevel(prev => Math.max(prev - 1, 0));
  const resetZoom = () => setZoomLevel(2); // 100%

  const currentZoom = ZOOM_LEVELS[zoomLevel];
  const zoomPercent = Math.round(currentZoom * 100);

  const viewportTelemetry = useMemo(() => ({
    trackingState: telemetry?.tracking?.state ?? "IDLE",
    errorPx: telemetry?.performance?.instant_error_px ?? 0,
    azError: telemetry?.control?.error_x_deg ?? 0,
    elError: telemetry?.control?.error_y_deg ?? 0,
  }), [telemetry]);

  // Listen to command acknowledgements from backend WebSocket
  useEffect(() => {
    const unsub = wsService.onCommandResult((res: CommandResult) => {
      setLastAck(res);
      setApplying(false);
      const timer = setTimeout(() => {
        setLastAck((current) => (current === res ? null : current));
      }, 3000);
      return () => clearTimeout(timer);
    });
    return unsub;
  }, []);

  const buildDisturbancePayload = useCallback((d: DisturbanceState, atm: AtmosphereType) => ({
    atmosphere:      { type: atm, intensity: d.haze.enabled ? d.haze.level : (atm === "clear" ? 0 : 0.5) },
    gaussian:        { enabled: d.gaussian.enabled, sigma: d.gaussian.sigma },
    blur:            { enabled: d.blur.enabled, kernel_size: d.blur.kernel },
    camera_jitter:   { enabled: d.jitter.enabled, max_px: d.jitter.maxPx },
    platform_motion: { enabled: d.platformMotion.enabled, max_px: d.platformMotion.maxPx },
    low_light:       { enabled: d.lowLight.enabled, gamma: 2.2 },
    salt_pepper:     { enabled: d.saltPepper.enabled, probability: d.saltPepper.prob },
  }), []);

  const sendDisturbanceUpdate = useCallback((d: DisturbanceState, atm: AtmosphereType) => {
    wsService.updateDisturbances(buildDisturbancePayload(d, atm) as any);
  }, [buildDisturbancePayload]);

  const applyChanges = useCallback(() => {
    setApplying(true);
    // 1. Update Camera FOV and Beacon Size
    wsService.updateCamera({
      hfov_deg: hfov,
      vfov_deg: vfov,
      beacon_size_px: beaconSize,
    });

    // 2. Update Target Trajectory
    wsService.updateTrajectory({
      type: trajectory,
      speed_deg_s: speed,
      size_px: beaconSize,
      start_pan_deg: trajectory === "acceptance" ? 1.4 : undefined,
      start_tilt_deg: trajectory === "acceptance" ? 1.0 : undefined,
    });

    // 3. Update Disturbances
    sendDisturbanceUpdate(disturbances, atmosphere);
  }, [hfov, vfov, beaconSize, trajectory, speed, disturbances, atmosphere, sendDisturbanceUpdate]);

  const resetDisturbances = useCallback(() => {
    const cleared: DisturbanceState = {
      gaussian:       { enabled: false, sigma: 10 },
      saltPepper:     { enabled: false, prob: 0.01 },
      blur:           { enabled: false, kernel: 3 },
      jitter:         { enabled: false, maxPx: 5 },
      platformMotion: { enabled: false, maxPx: 3 },
      lowLight:       { enabled: false },
      haze:           { enabled: false, level: 0.35 },
    };
    setAtmosphere("clear");
    setDisturbances(cleared);
    sendDisturbanceUpdate(cleared, "clear");
  }, [sendDisturbanceUpdate]);

  const toggleDisturbance = useCallback((key: keyof DisturbanceState, enabled: boolean) => {
    setDisturbances((prev) => {
      const updated = {
        ...prev,
        [key]: { ...(prev[key] as any), enabled },
      };
      sendDisturbanceUpdate(updated, atmosphere);
      return updated;
    });
  }, [atmosphere, sendDisturbanceUpdate]);

  const selectAtmosphere = useCallback((type: AtmosphereType) => {
    setAtmosphere(type);
    sendDisturbanceUpdate(disturbances, type);
  }, [disturbances, sendDisturbanceUpdate]);

  const activeDisturbanceList = (() => {
    const active: string[] = [];
    if (atmosphere !== "clear") active.push(`ATMOSPHERE: ${atmosphere.toUpperCase()}`);
    // atmosphere is always defined (initialized to "clear"), but guard anyway
    if (disturbances.gaussian.enabled)       active.push(`GAUSSIAN  σ = ${disturbances.gaussian.sigma}`);
    if (disturbances.saltPepper.enabled)     active.push(`SALT & PEPPER  p = ${disturbances.saltPepper.prob}`);
    if (disturbances.blur.enabled)           active.push(`BLUR  k = ${disturbances.blur.kernel}`);
    if (disturbances.jitter.enabled)         active.push(`CAM JITTER  ±${disturbances.jitter.maxPx} px`);
    if (disturbances.platformMotion.enabled) active.push(`PLATFORM MOTION  ±${disturbances.platformMotion.maxPx} px`);
    if (disturbances.lowLight.enabled)       active.push("LOW LIGHT");
    if (disturbances.haze.enabled)           active.push(`HAZE  lvl = ${disturbances.haze.level.toFixed(2)}`);
    return active;
  })();

  return (
    <div className="flex flex-1 w-full h-full min-h-0 max-h-full overflow-hidden bg-[#070B12]">
      {/* ─ Left: Virtual Camera Viewport + Active status ───────── */}
      <div className="flex-1 min-w-0 min-h-0 flex flex-col p-4 gap-3 overflow-hidden">

        {/* Viewport Header */}
        <div className="flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <span className="section-label">Virtual Camera Viewport</span>
            {lastAck && (
              <span className={`flex items-center gap-1 font-mono text-[10px] px-2 py-0.5 rounded border transition-opacity ${
                lastAck.status === "applied"
                  ? "bg-[#102A1E] text-[#4EBA6F] border-[#1E523A]"
                  : "bg-[#331111] text-[#F87171] border-[#5E2222]"
              }`}>
                {lastAck.status === "applied" ? (
                  <CheckCircle2 className="w-3 h-3 text-[#4EBA6F]" />
                ) : (
                  <AlertCircle className="w-3 h-3 text-[#F87171]" />
                )}
                {lastAck.command}: {lastAck.status?.toUpperCase() ?? "UNKNOWN"}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] text-[#738397]">SIMULATION CLOSED-LOOP</span>

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
              <ControlButton
                variant="tertiary"
                size="sm"
                icon={<RotateCcw />}
                onClick={resetZoom}
                title="Reset zoom"
              >
                RESET
              </ControlButton>
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
            <TrackingCanvas telemetry={telemetry ?? null} />
          </div>
        </FullscreenContainer>

        {/* Active Disturbances summary */}
        <PanelSection level={1} padding="sm" className="flex-shrink-0">
          <SectionHeader title="Active Disturbances" className="mb-2" />
          {activeDisturbanceList.length === 0 ? (
            <p className="font-sans text-[12px] text-[#738397]">No disturbances active — optical environment is clear.</p>
          ) : (
            <ul className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 max-h-24 overflow-y-auto">
              {activeDisturbanceList.map((d) => (
                <li key={d} className="flex items-center gap-2 bg-[#0B111B] px-2 py-1 rounded border border-[#1A2839]">
                  <span className="status-dot bg-[#D99A24]" />
                  <span className="font-mono text-[11px] text-[#AAB7C5]">{d}</span>
                </li>
              ))}
            </ul>
          )}
        </PanelSection>
      </div>

      {/* ─ Right: Simulation Controls Panel ───────────────────────── */}
      <div
        className="flex-shrink-0 flex flex-col border-l border-[#26364A] bg-[#0B111B] overflow-hidden h-full max-h-full min-h-0"
        style={{ width: 310 }}
      >
        <div className="p-4 pb-3 flex-shrink-0 border-b border-[#1B2839]">
          <PageHeader title="Simulation Control" />
        </div>

        {/* Scrollable Controls Content */}
        <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
          {/* Trajectory & Camera */}
          <PanelSection level={1} padding="sm">
            <SectionHeader title="Target Motion" className="mb-2" />
            <div className="relative">
              <select
                value={trajectory}
                onChange={(e) => setTrajectory(e.target.value as TrajectoryType)}
                className="w-full pr-8 appearance-none bg-[#070B12] border border-[#26364A] text-[#E8EDF3] text-[12px] rounded px-2.5 py-1.5 focus:border-[#1F78B4] focus:outline-none"
                aria-label="Select trajectory type"
              >
                {TRAJECTORIES.map(({ id, label }) => (
                  <option key={id} value={id}>{label}</option>
                ))}
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#738397] pointer-events-none" />
            </div>

            <div className="mt-3 space-y-3">
              <SliderField
                label="Speed"
                value={speed}
                unit="deg/s"
                min={0.5} max={10} step={0.5}
                onChange={(v) => setSpeed(v)}
              />
              <SliderField
                label="Beacon Size"
                value={beaconSize}
                unit="px"
                min={4} max={30} step={1}
                onChange={(v) => setBeaconSize(v)}
              />
            </div>
          </PanelSection>

          {/* Camera Field of View */}
          <PanelSection level={1} padding="sm">
            <SectionHeader title="Virtual Camera" className="mb-2" />
            <div className="space-y-3">
              <SliderField
                label="HFOV"
                value={hfov}
                unit="°"
                min={1} max={10} step={0.5}
                onChange={(v) => setHfov(v)}
              />
              <SliderField
                label="VFOV"
                value={vfov}
                unit="°"
                min={1} max={10} step={0.5}
                onChange={(v) => setVfov(v)}
              />
            </div>
          </PanelSection>

          {/* Atmospheric condition */}
          <PanelSection level={1} padding="sm">
            <SectionHeader title="Atmosphere" className="mb-2" />
            <div className="grid grid-cols-2 gap-1.5">
              {(["clear", "haze", "fog", "rain"] as AtmosphereType[]).map((type) => (
                <button
                  key={type}
                  onClick={() => selectAtmosphere(type)}
                  className={`px-2 py-1.5 rounded font-sans text-[11px] font-medium transition-colors duration-150 border ${
                    atmosphere === type
                      ? "bg-[#155A8A] border-[#1F78B4] text-[#E8EDF3]"
                      : "bg-transparent border-[#26364A] text-[#738397] hover:text-[#AAB7C5] hover:border-[#34475E]"
                  }`}
                >
                  {type.toUpperCase()}
                </button>
              ))}
            </div>
          </PanelSection>

          {/* Disturbance checkboxes */}
          <PanelSection level={1} padding="sm">
            <SectionHeader title="Disturbances" className="mb-2" />
            <div className="space-y-2">
              {[
                { key: "gaussian" as const,       label: "Gaussian Noise",       subtext: `σ = ${disturbances.gaussian.sigma}` },
                { key: "saltPepper" as const,     label: "Salt & Pepper",         subtext: `p = ${disturbances.saltPepper.prob}` },
                { key: "blur" as const,            label: "Defocus / Blur",        subtext: `k = ${disturbances.blur.kernel}` },
                { key: "jitter" as const,          label: "Camera Jitter",         subtext: `±${disturbances.jitter.maxPx} px` },
                { key: "platformMotion" as const,  label: "Platform Motion",       subtext: `±${disturbances.platformMotion.maxPx} px` },
                { key: "lowLight" as const,        label: "Low Light",             subtext: "" },
                { key: "haze" as const,            label: "Haze / Scattering",    subtext: `lvl = ${disturbances.haze.level.toFixed(2)}` },
              ].map(({ key, label, subtext }) => {
                const d = disturbances[key] as { enabled: boolean };
                return (
                  <label
                    key={key}
                    className="flex items-center justify-between cursor-pointer"
                  >
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={d.enabled}
                        onChange={(e) => toggleDisturbance(key, e.target.checked)}
                        aria-label={`Enable ${label}`}
                        className="rounded border-[#26364A] bg-[#070B12] text-[#1F78B4] focus:ring-0"
                      />
                      <span className="font-sans text-[12px] text-[#AAB7C5]">{label}</span>
                    </div>
                    {d.enabled && subtext && (
                      <span className="font-mono text-[10px] text-[#738397]">{subtext}</span>
                    )}
                  </label>
                );
              })}
            </div>
          </PanelSection>
        </div>

        {/* Sticky Action Footer */}
        <div className="flex-shrink-0 p-4 pt-3 border-t border-[#26364A] bg-[#0B111B] flex gap-2 shadow-lg z-10">
          <ControlButton
            variant="secondary"
            icon={<RotateCcw />}
            onClick={resetDisturbances}
            className="flex-1 whitespace-nowrap"
            disabled={applying}
          >
            RESET
          </ControlButton>
          <ControlButton
            variant="primary"
            icon={<Play />}
            onClick={applyChanges}
            className="flex-1 whitespace-nowrap"
            disabled={applying}
          >
            {applying ? "APPLYING..." : "APPLY"}
          </ControlButton>
        </div>
      </div>
    </div>
  );
};

/* ── Sub-components ─────────────────────────────────────────────── */

interface SliderFieldProps {
  label: string;
  value: number;
  unit: string;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  disabled?: boolean;
}

const SliderField: React.FC<SliderFieldProps> = ({
  label, value, unit, min, max, step, onChange, disabled = false,
}) => (
  <div className="space-y-1">
    <div className="flex items-center justify-between">
      <span className="font-sans text-[11px] text-[#738397]">{label}</span>
      <span className="font-mono text-[12px] text-[#AAB7C5]">
        {value} <span className="text-[#738397]">{unit}</span>
      </span>
    </div>
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(Number(e.target.value))}
      className="w-full"
      aria-label={`${label} value ${value} ${unit}`}
    />
  </div>
);