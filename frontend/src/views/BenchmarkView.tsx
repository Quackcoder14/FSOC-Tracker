import React, { useState, useCallback } from "react";
import { wsService } from "../services/websocket";
import { TelemetryPacket } from "../types/telemetry";
import { ControlButton } from "../components/ui/ControlButton";
import { SectionHeader, PageHeader } from "../components/ui/SectionHeader";
import { PanelSection } from "../components/ui/PanelSection";
import { MetricRow } from "../components/ui/MetricRow";
import {
  Play,
  RotateCcw,
  Pause,
  SkipForward,
  FolderOpen,
  FileText,
  Download,
  AlertCircle,
  Upload,
  Loader2,
  ChevronDown,
  ChevronUp,
  ExternalLink,
} from "lucide-react";

const HTTP_UPLOAD_URL = "http://127.0.0.1:8766";

interface BenchmarkViewProps {
  telemetry: TelemetryPacket | null;
  onNavigateToResults?: () => void;
}

type PassStatus = "pass" | "fail" | "pending" | "not_run";

interface CriterionRow {
  name: string;
  target: string;
  measured: string | null;
  status: PassStatus;
}

interface BenchmarkResult {
  rmse: number | null;
  lock: number | null;
  fps: number | null;
  latency: number | null;
  frame: number | null;
  acquisitionTime: number | null;
  reacquisitionTime: number | null;
  lockRetention: number | null;
  framesProcessed: number;
  framesEvaluated: number;
}

// Describes a selected file — either a browser File or a manually typed path
interface FileSelection {
  /** Display name shown in the input */
  displayName: string;
  /** Server-side path (set after upload, or typed directly) */
  serverPath: string | null;
  /** The browser File object when selected via picker (null if typed) */
  file: File | null;
  /** Whether this needs uploading before use */
  needsUpload: boolean;
}

function makeSelection(displayName: string): FileSelection {
  return { displayName, serverPath: displayName || null, file: null, needsUpload: false };
}

/** Upload a File to the backend and return the server-side path */
async function uploadFile(file: File, endpoint: "video" | "gt"): Promise<string> {
  const form = new FormData();
  form.append("file", file);

  let resp: Response;
  try {
    resp = await fetch(`${HTTP_UPLOAD_URL}/upload/${endpoint}`, {
      method: "POST",
      body: form,
    });
  } catch (networkErr: any) {
    // "Failed to fetch" means the HTTP server is not reachable
    throw new Error(
      `Cannot reach the upload server at ${HTTP_UPLOAD_URL}. ` +
      `Make sure the backend is running (python main.py) and has been restarted ` +
      `after the latest changes. Port 8766 must be open.`
    );
  }

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.error || `Upload failed (HTTP ${resp.status})`);
  }

  const json = await resp.json();
  if (!json.ok || !json.path) {
    throw new Error(json.error || "Server returned no path");
  }
  return json.path as string;
}

export const BenchmarkView: React.FC<BenchmarkViewProps> = ({ telemetry, onNavigateToResults }) => {
  const [videoSel, setVideoSel] = useState<FileSelection>(
    makeSelection("data/demo/clean/clean_trajectory.mp4")
  );
  const [gtSel, setGtSel] = useState<FileSelection>(
    makeSelection("data/demo/clean/ground_truth.csv")
  );

  const [benchmarkState, setBenchmarkState] = useState<
    "ready" | "uploading" | "running" | "paused" | "completed" | "failed"
  >("ready");
  const [uploadProgress, setUploadProgress] = useState<string>("");
  const [result, setResult] = useState<BenchmarkResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  // ── File pickers ──────────────────────────────────────────────────────

  const openBrowserPicker = useCallback(
    (accept: string, onFile: (f: File) => void) => {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = accept;
      input.onchange = (ev: Event) => {
        const file = (ev.target as HTMLInputElement)?.files?.[0];
        if (file) onFile(file);
      };
      input.click();
    },
    []
  );

  const selectVideoFile = useCallback(() => {
    openBrowserPicker(".mp4,.mkv,.avi,.mov", (file) => {
      setVideoSel({
        displayName: file.name,
        serverPath: null,
        file,
        needsUpload: true,
      });
    });
  }, [openBrowserPicker]);

  const selectGtFile = useCallback(() => {
    openBrowserPicker(".csv,.json", (file) => {
      setGtSel({
        displayName: file.name,
        serverPath: null,
        file,
        needsUpload: true,
      });
    });
  }, [openBrowserPicker]);

  // ── WebSocket listeners ───────────────────────────────────────────────

  React.useEffect(() => {
    const unsubCmd = wsService.onCommandResult((res) => {
      if (res.type === "COMMAND_ERROR") {
        setBenchmarkState("failed");
        setErrorMessage(`BENCHMARK FAILED: ${res.error || "Unknown error"}`);
      }
    });
    const unsubStatus = wsService.onStatus((status) => {
      if (status.completed || (status.running === false && benchmarkState === "running")) {
        setBenchmarkState("completed");
      }
    });
    return () => {
      unsubCmd();
      unsubStatus();
    };
  }, [benchmarkState]);

  // ── Benchmark control ─────────────────────────────────────────────────

  const startBenchmark = useCallback(async () => {
    setBenchmarkState("uploading");
    setErrorMessage(null);
    setResult(null);

    try {
      // 1. Upload video if it came from the browser file picker
      let videoPath = videoSel.serverPath;
      if (videoSel.needsUpload && videoSel.file) {
        setUploadProgress("Uploading video…");
        videoPath = await uploadFile(videoSel.file, "video");
        setVideoSel((prev) => ({ ...prev, serverPath: videoPath, needsUpload: false }));
      }

      if (!videoPath) {
        throw new Error("No video path specified. Please select or type a video path.");
      }

      // 2. Upload ground truth if it came from the browser file picker
      let gtPath: string | undefined;
      if (gtSel.displayName) {
        if (gtSel.needsUpload && gtSel.file) {
          setUploadProgress("Uploading ground truth…");
          gtPath = await uploadFile(gtSel.file, "gt");
          setGtSel((prev) => ({ ...prev, serverPath: gtPath!, needsUpload: false }));
        } else {
          gtPath = gtSel.serverPath ?? undefined;
        }
      }

      setUploadProgress("");

      // Validate video is selected
      if (!videoPath) {
        setBenchmarkState("failed");
        setErrorMessage("ERROR: No video file selected. Please select a video file before starting the benchmark.");
        return;
      }

      // 3. Configure benchmark mode on the backend with the server-side paths
      wsService.setMode("benchmark", videoPath, gtPath);

      // 4. Small delay to let SET_MODE be processed before START_BENCHMARK
      await new Promise<void>((resolve) => setTimeout(resolve, 150));

      // 5. Start benchmark — backend uses VideoFileSource, NOT simulation engine
      setBenchmarkState("running");
      wsService.startBenchmark();
    } catch (err: any) {
      setBenchmarkState("failed");
      setUploadProgress("");
      setErrorMessage(`ERROR: ${err?.message ?? String(err)}`);
    }
  }, [videoSel, gtSel]);

  const resetBenchmark = useCallback(() => {
    wsService.stop();
    setBenchmarkState("ready");
    setResult(null);
    setErrorMessage(null);
    setUploadProgress("");
  }, []);

  const pauseBenchmark = useCallback(() => {
    wsService.pause();
    setBenchmarkState("paused");
  }, []);

  const resumeBenchmark = useCallback(() => {
    wsService.resume();
    setBenchmarkState("running");
  }, []);

  const stepBenchmark = useCallback(() => {
    wsService.step();
  }, []);

  // ── Telemetry → result ────────────────────────────────────────────────

  React.useEffect(() => {
    if (benchmarkState === "running" && telemetry) {
      const rmse = telemetry.performance?.rmse_px ?? null;
      const lock = telemetry.performance?.lock_retention_pct ?? null;
      const fps = telemetry.performance?.fps ?? null;
      const latency = telemetry.performance?.latency_ms ?? null;
      const frame = telemetry.frame_index ?? null;

      if (frame !== null && frame >= 0) {
        setResult({
          rmse,
          lock,
          fps,
          latency,
          frame,
          acquisitionTime: null,
          reacquisitionTime: null,
          lockRetention: lock,
          framesProcessed: frame + 1,
          framesEvaluated: frame + 1,
        });
      }
    }
  }, [telemetry, benchmarkState]);

  // ── Derived metrics ───────────────────────────────────────────────────

  const rmse = result?.rmse ?? telemetry?.performance?.rmse_px ?? null;
  const lock = result?.lock ?? telemetry?.performance?.lock_retention_pct ?? null;
  const fps = result?.fps ?? telemetry?.performance?.fps ?? null;
  const latency = result?.latency ?? telemetry?.performance?.latency_ms ?? null;

  const criteria = React.useMemo<CriterionRow[]>(
    () => [
      {
        name: "RMSE",
        target: "≤ 10.0 px",
        measured:
          rmse !== null
            ? `${rmse.toFixed(2)} px`
            : benchmarkState === "completed"
            ? "—"
            : "NOT RUN",
        status:
          benchmarkState === "completed"
            ? rmse !== null
              ? rmse <= 10.0
                ? "pass"
                : "fail"
              : "fail"
            : "not_run",
      },
      {
        name: "Lock Retention",
        target: "≥ 90.0 %",
        measured:
          lock !== null
            ? `${lock.toFixed(1)} %`
            : benchmarkState === "completed"
            ? "—"
            : "NOT RUN",
        status:
          benchmarkState === "completed"
            ? lock !== null
              ? lock >= 90.0
                ? "pass"
                : "fail"
              : "fail"
            : "not_run",
      },
      {
        name: "Processing Throughput",
        target: "≥ 20.0 FPS",
        measured:
          fps !== null
            ? `${fps.toFixed(1)} FPS`
            : benchmarkState === "completed"
            ? "—"
            : "NOT RUN",
        status:
          benchmarkState === "completed"
            ? fps !== null
              ? fps >= 20.0
                ? "pass"
                : "fail"
              : "fail"
            : "not_run",
      },
      {
        name: "P95 Frame Latency",
        target: "≤ 50.0 ms",
        measured:
          latency !== null
            ? `${latency.toFixed(1)} ms`
            : benchmarkState === "completed"
            ? "—"
            : "NOT RUN",
        status:
          benchmarkState === "completed"
            ? latency !== null
              ? latency <= 50.0
                ? "pass"
                : "fail"
              : "fail"
            : "not_run",
      },
    ],
    [rmse, lock, fps, latency, benchmarkState]
  );

  const allPass = criteria.every((c) => c.status === "pass");
  const anyFail = criteria.some((c) => c.status === "fail");

  const overallStatus: "pass" | "fail" | "pending" | "not_run" =
    benchmarkState === "completed"
      ? anyFail
        ? "fail"
        : allPass
        ? "pass"
        : "fail"
      : "not_run";

  const isRunning = benchmarkState === "running";
  const isUploading = benchmarkState === "uploading";
  const canStart =
    benchmarkState !== "running" && benchmarkState !== "uploading";
  const canPause = benchmarkState === "running";
  const canResume = benchmarkState === "paused";
  const canStep = benchmarkState === "running" || benchmarkState === "paused";

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full min-h-0 bg-[#070B12] selectable">
      {/* Header */}
      <div className="flex-shrink-0 px-4 border-b border-[#26364A] bg-[#0B111B]">
        <PageHeader
          title="Benchmark / Standard Verification"
          subtitle="Upload a test video and optional ground truth, then run the benchmark independently of the simulation engine."
          action={
            <div className="flex items-center gap-2">
              <ControlButton
                variant="secondary"
                icon={<RotateCcw />}
                onClick={resetBenchmark}
                size="md"
              >
                RESET
              </ControlButton>
              {canPause && (
                <ControlButton
                  variant="secondary"
                  icon={<Pause />}
                  onClick={pauseBenchmark}
                  size="md"
                >
                  PAUSE
                </ControlButton>
              )}
              {canResume && (
                <ControlButton
                  variant="secondary"
                  icon={<Play />}
                  onClick={resumeBenchmark}
                  size="md"
                >
                  RESUME
                </ControlButton>
              )}
              <ControlButton
                variant="secondary"
                icon={<SkipForward />}
                onClick={stepBenchmark}
                size="md"
                disabled={!canStep}
              >
                STEP
              </ControlButton>
              <div className="relative">
                <div
                  className="absolute left-0 top-1 bottom-1 w-[3px] rounded-r"
                  style={{ backgroundColor: "#F28C28" }}
                  aria-hidden="true"
                />
                <ControlButton
                  variant="primary"
                  icon={
                    isUploading ? (
                      <Loader2 className="animate-spin" />
                    ) : (
                      <Play />
                    )
                  }
                  onClick={startBenchmark}
                  size="md"
                  className="pl-5"
                  disabled={!canStart}
                >
                  {isUploading
                    ? "UPLOADING…"
                    : isRunning
                    ? "RUNNING…"
                    : "RUN BENCHMARK"}
                </ControlButton>
              </div>
            </div>
          }
        />
      </div>

      {/* Scrollable content */}
      <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">

        {/* Status bar */}
        <div className="flex items-center gap-4 flex-wrap p-3 bg-[#0B111B] rounded border border-[#26364A]">
          <div className="flex items-center gap-2">
            <span className="font-sans text-[11px] text-[#738397] uppercase tracking-wide">STATUS</span>
            <span
              className={`px-2 py-1 rounded font-mono text-[11px] font-medium ${
                benchmarkState === "uploading"
                  ? "bg-[#1E2A10] text-[#A3D95C]"
                  : benchmarkState === "running"
                  ? "bg-[#155A8A] text-[#1F78B4]"
                  : benchmarkState === "completed"
                  ? "bg-[#102A1E] text-[#4EBA6F]"
                  : benchmarkState === "failed"
                  ? "bg-[#331111] text-[#F87171]"
                  : benchmarkState === "paused"
                  ? "bg-[#2D2A0E] text-[#D99A24]"
                  : "bg-[#1A2839] text-[#738397]"
              }`}
            >
              {benchmarkState === "uploading" ? "UPLOADING" : benchmarkState.toUpperCase()}
            </span>
          </div>

          {/* Upload progress */}
          {isUploading && uploadProgress && (
            <div className="flex items-center gap-2 text-[#A3D95C]">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span className="font-sans text-[11px]">{uploadProgress}</span>
            </div>
          )}

          {/* Running frame counter */}
          {isRunning && result && (
            <div className="flex items-center gap-4 text-[11px]">
              <span className="font-sans text-[#738397]">FRAME</span>
              <span className="font-mono text-[#AAB7C5] selectable">{result.framesProcessed}</span>
              <span className="font-sans text-[#738397]">ENGINE</span>
              <span className="font-mono text-[#AAB7C5] selectable">
                {(telemetry?.performance?.fps ?? 0).toFixed(1)} FPS
              </span>
              <span className="font-sans text-[#738397]">SOURCE</span>
              <span className="font-mono text-[#AAB7C5] selectable">VIDEO FILE</span>
            </div>
          )}

          {/* Error message */}
          {errorMessage && (
            <div className="flex items-center gap-2 text-[#F87171]">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span className="font-sans text-[11px] selectable">{errorMessage}</span>
            </div>
          )}
        </div>

        {/* ── Source Input ───────────────────────────────────────────── */}
        <PanelSection level={1} padding="md">
          <SectionHeader title="Source Input" className="mb-3" />

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Video */}
            <div className="space-y-1.5">
              <label
                htmlFor="bench-video-path"
                className="font-sans text-[11px] uppercase tracking-[0.05em] text-[#738397]"
              >
                Video Input
              </label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <input
                    id="bench-video-path"
                    type="text"
                    value={videoSel.displayName}
                    onChange={(e) =>
                      setVideoSel(makeSelection(e.target.value))
                    }
                    placeholder="Select a video file or type a server path…"
                    className="w-full selectable"
                    aria-label="Video file path"
                  />
                  {videoSel.needsUpload && (
                    <span
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-mono text-[#A3D95C] bg-[#1E2A10] px-1.5 py-0.5 rounded pointer-events-none"
                      title="File selected — will be uploaded when benchmark starts"
                    >
                      READY TO UPLOAD
                    </span>
                  )}
                  {!videoSel.needsUpload && videoSel.serverPath && (
                    <span
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-mono text-[#4EBA6F] bg-[#102A1E] px-1.5 py-0.5 rounded pointer-events-none"
                      title="Using server-side path directly"
                    >
                      SERVER PATH
                    </span>
                  )}
                </div>
                <ControlButton
                  variant="secondary"
                  icon={<FolderOpen />}
                  size="md"
                  title="Browse for video file"
                  onClick={selectVideoFile}
                  disabled={isUploading || isRunning}
                >
                  BROWSE
                </ControlButton>
              </div>
              <p className="font-sans text-[10px] text-[#4A5E72]">
                Supported: MP4, MKV, AVI, MOV. File will be uploaded to the backend when you start the benchmark.
              </p>
            </div>

            {/* Ground Truth */}
            <div className="space-y-1.5">
              <label
                htmlFor="bench-gt-path"
                className="font-sans text-[11px] uppercase tracking-[0.05em] text-[#738397]"
              >
                Ground Truth <span className="normal-case text-[#4A5E72]">(optional)</span>
              </label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <input
                    id="bench-gt-path"
                    type="text"
                    value={gtSel.displayName}
                    onChange={(e) =>
                      setGtSel(makeSelection(e.target.value))
                    }
                    placeholder="Select a CSV/JSON file or type a server path…"
                    className="w-full selectable"
                    aria-label="Ground truth CSV path"
                  />
                  {gtSel.needsUpload && (
                    <span
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-mono text-[#A3D95C] bg-[#1E2A10] px-1.5 py-0.5 rounded pointer-events-none"
                      title="File selected — will be uploaded when benchmark starts"
                    >
                      READY TO UPLOAD
                    </span>
                  )}
                </div>
                <ControlButton
                  variant="secondary"
                  icon={<FolderOpen />}
                  size="md"
                  title="Browse for ground truth file"
                  onClick={selectGtFile}
                  disabled={isUploading || isRunning}
                >
                  BROWSE
                </ControlButton>
              </div>
              <p className="font-sans text-[10px] text-[#4A5E72]">
                Supported: CSV, JSON. Leave blank to run without accuracy scoring.
              </p>
            </div>
          </div>
        </PanelSection>

        {/* ── Source Properties ─────────────────────────────────────────── */}
        <PanelSection level={1} padding="md">
          <SectionHeader title="Source Properties" className="mb-3" />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-x-8 gap-y-2">
            <MetricRow label="Resolution" value="640 × 480" />
            <MetricRow label="Frame Rate" value="30.0" unit="FPS" />
            <MetricRow
              label="Frames"
              value={result?.framesProcessed ?? "—"}
            />
            <MetricRow
              label="Duration"
              value={
                result?.framesProcessed
                  ? (result.framesProcessed / 30).toFixed(1)
                  : "—"
              }
              unit="s"
            />
            <MetricRow
              label="Ground Truth"
              value={gtSel.displayName ? "PROVIDED" : "NOT SET"}
              valueColor={gtSel.displayName ? "text-[#38A169]" : "text-[#738397]"}
            />
            <MetricRow
              label="Source State"
              value={
                benchmarkState === "uploading"
                  ? "UPLOADING"
                  : benchmarkState === "running"
                  ? "RUNNING"
                  : benchmarkState === "completed"
                  ? "COMPLETED"
                  : "READY"
              }
              valueColor={
                benchmarkState === "uploading"
                  ? "text-[#A3D95C]"
                  : benchmarkState === "running"
                  ? "text-[#F28C28]"
                  : benchmarkState === "completed"
                  ? "text-[#38A169]"
                  : "text-[#38A169]"
              }
            />
            <MetricRow
              label="Engine Mode"
              value="VIDEO FILE"
              valueColor="text-[#738397]"
            />
            <MetricRow
              label="Simulation"
              value="DISCONNECTED"
              valueColor="text-[#4A5E72]"
            />
          </div>
        </PanelSection>

        {/* ── Verification Results ───────────────────────────────────────── */}
        <PanelSection level={1} padding="none">
          <div className="px-4 pt-4 pb-2">
            <SectionHeader title="Verification Results" />
          </div>

          <div className="overflow-x-auto">
            <table
              className="w-full text-left border-collapse"
              role="table"
              aria-label="Benchmark verification results"
            >
              <thead>
                <tr className="border-b border-[#26364A]">
                  <th className="px-4 py-2.5 font-sans font-medium text-[11px] uppercase tracking-[0.05em] text-[#738397]">
                    Metric
                  </th>
                  <th className="px-4 py-2.5 font-sans font-medium text-[11px] uppercase tracking-[0.05em] text-[#738397] text-right">
                    Target
                  </th>
                  <th className="px-4 py-2.5 font-sans font-medium text-[11px] uppercase tracking-[0.05em] text-[#738397] text-right">
                    Measured
                  </th>
                  <th className="px-4 py-2.5 font-sans font-medium text-[11px] uppercase tracking-[0.05em] text-[#738397] text-right pr-4">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody>
                {criteria.map((row, idx) => (
                  <tr
                    key={row.name}
                    className={`border-b border-[#1B2839] ${
                      idx % 2 === 0 ? "bg-[#0f1724]" : ""
                    }`}
                  >
                    <td className="px-4 py-2.5 font-sans text-[13px] text-[#E8EDF3] selectable">
                      {row.name}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[12px] text-[#738397] text-right selectable">
                      {row.target}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[13px] text-[#E8EDF3] font-medium text-right selectable">
                      {row.measured}
                    </td>
                    <td className="px-4 py-2.5 text-right pr-4">
                      <StatusCell status={row.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Overall indicator */}
          <div className="px-4 py-2.5 border-t border-[#26364A] flex items-center justify-between">
            <span className="font-sans text-[11px] text-[#738397] uppercase tracking-wide">
              Overall Result
            </span>
            <OverallStatus status={overallStatus} />
          </div>
        </PanelSection>

        {/* ── Run Summary ────────────────────────────────────────────────── */}
        <PanelSection level={1} padding="md">
          <SectionHeader title="Run Summary" className="mb-3" />
          <div className="grid grid-cols-2 md:grid-cols-5 gap-x-8 gap-y-2 mb-4">
            <MetricRow label="Frames Processed" value={result?.framesProcessed ?? "—"} />
            <MetricRow label="Frames Evaluated" value={result?.framesEvaluated ?? "—"} />
            <MetricRow label="RMSE" value={result?.rmse?.toFixed(2)} unit="px" />
            <MetricRow label="Lock Ret." value={result?.lock?.toFixed(1)} unit="%" />
            <MetricRow
              label="Throughput"
              value={(telemetry?.performance?.fps ?? 0).toFixed(1)}
              unit="FPS"
            />
          </div>
          <div className="flex items-center gap-2 pt-3 border-t border-[#26364A]">
            {/* VIEW DETAILS — toggles expanded metrics panel */}
            <ControlButton
              variant="secondary"
              icon={showDetails ? <ChevronUp /> : <ChevronDown />}
              size="sm"
              onClick={() => setShowDetails((v) => !v)}
              disabled={!result}
            >
              VIEW DETAILS
            </ControlButton>

            {/* OPEN REPORT — generate report then navigate to Results tab */}
            <ControlButton
              variant="secondary"
              icon={<ExternalLink />}
              size="sm"
              disabled={benchmarkState !== "completed" && benchmarkState !== "failed"}
              onClick={() => {
                wsService.generateReport();
                onNavigateToResults?.();
              }}
            >
              OPEN REPORT
            </ControlButton>

            {/* EXPORT RESULTS — download CSV of this run */}
            <ControlButton
              variant="secondary"
              icon={<Download />}
              size="sm"
              disabled={!result}
              onClick={() => {
                if (!result) return;
                const rows = [
                  ["Metric", "Value", "Unit"],
                  ["RMSE", result.rmse?.toFixed(3) ?? "", "px"],
                  ["Lock Retention", result.lock?.toFixed(2) ?? "", "%"],
                  ["Throughput", result.fps?.toFixed(2) ?? "", "FPS"],
                  ["P95 Latency", result.latency?.toFixed(2) ?? "", "ms"],
                  ["Frames Processed", String(result.framesProcessed), ""],
                  ["Frames Evaluated", String(result.framesEvaluated), ""],
                  ["Video Source", videoSel.displayName, ""],
                  ["Ground Truth", gtSel.displayName || "none", ""],
                  ["Run Timestamp", new Date().toISOString(), ""],
                ];
                const csv = rows.map((r) => r.map((c) => `"${c}"`).join(",")).join("\n");
                const blob = new Blob([csv], { type: "text/csv" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `benchmark_results_${Date.now()}.csv`;
                a.click();
                URL.revokeObjectURL(url);
              }}
            >
              EXPORT RESULTS
            </ControlButton>
          </div>

          {/* ── Expanded Details Panel ─────────────────────────── */}
          {showDetails && result && (
            <div className="mt-4 pt-4 border-t border-[#26364A] space-y-3">
              <SectionHeader title="Full Run Details" className="mb-3" />
              <div className="grid grid-cols-2 md:grid-cols-4 gap-x-8 gap-y-2">
                <MetricRow label="RMSE" value={result.rmse?.toFixed(3) ?? "—"} unit="px" />
                <MetricRow label="Mean Error" value={telemetry?.performance?.instant_error_px?.toFixed(2) ?? "—"} unit="px" />
                <MetricRow label="Lock Retention" value={result.lock?.toFixed(2) ?? "—"} unit="%" />
                <MetricRow label="Throughput" value={result.fps?.toFixed(2) ?? "—"} unit="FPS" />
                <MetricRow label="P95 Latency" value={result.latency?.toFixed(2) ?? "—"} unit="ms" />
                <MetricRow label="Frames Total" value={result.framesProcessed} />
                <MetricRow label="Frames Tracked" value={result.framesEvaluated} />
                <MetricRow label="Target Losses" value={telemetry?.performance?.fps !== undefined ? "—" : "—"} />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-1 pt-2 border-t border-[#1B2839]">
                <MetricRow
                  label="Video Source"
                  value={videoSel.displayName}
                  valueColor="text-[#4B93C3]"
                />
                <MetricRow
                  label="Ground Truth"
                  value={gtSel.displayName || "none"}
                  valueColor={gtSel.displayName ? "text-[#4B93C3]" : "text-[#738397]"}
                />
              </div>
            </div>
          )}
        </PanelSection>

        {/* ── Empty State ────────────────────────────────────────────────── */}
        {benchmarkState === "ready" && (
          <PanelSection level={1} padding="md">
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Upload className="w-12 h-12 text-[#738397] mb-3" />
              <h3 className="font-sans text-[14px] text-[#E8EDF3] mb-1">
                UPLOAD A VIDEO TO BEGIN
              </h3>
              <p className="font-sans text-[12px] text-[#738397] max-w-md">
                Click <strong>BROWSE</strong> to select a local video file, then click{" "}
                <strong>RUN BENCHMARK</strong>. The file will be uploaded to the backend automatically.
                No simulation engine is involved.
              </p>
            </div>
          </PanelSection>
        )}
      </div>
    </div>
  );
};

/* ── Sub-components ─────────────────────────────────────────────────── */

const StatusCell: React.FC<{ status: PassStatus }> = ({ status }) => {
  if (status === "pass") {
    return (
      <span className="inline-flex items-center gap-1.5 font-sans font-medium text-[12px] text-[#38A169]">
        <span aria-hidden="true">✓</span> PASS
      </span>
    );
  }
  if (status === "fail") {
    return (
      <span className="inline-flex items-center gap-1.5 font-sans font-medium text-[12px] text-[#D9534F]">
        <span aria-hidden="true">✕</span> FAIL
      </span>
    );
  }
  if (status === "not_run") {
    return (
      <span className="inline-flex items-center gap-1.5 font-sans font-medium text-[12px] text-[#738397]">
        NOT RUN
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 font-sans text-[12px] text-[#738397]">
      —
    </span>
  );
};

const OverallStatus: React.FC<{
  status: "pass" | "fail" | "pending" | "not_run";
}> = ({ status }) => {
  if (status === "pass") {
    return (
      <span className="inline-flex items-center gap-1.5 font-sans font-semibold text-[13px] text-[#38A169]">
        <span className="status-dot bg-[#38A169]" /> ALL PASS
      </span>
    );
  }
  if (status === "fail") {
    return (
      <span className="inline-flex items-center gap-1.5 font-sans font-semibold text-[13px] text-[#D9534F]">
        <span className="status-dot bg-[#D9534F]" /> CRITERIA NOT MET
      </span>
    );
  }
  if (status === "not_run") {
    return (
      <span className="inline-flex items-center gap-1.5 font-sans text-[12px] text-[#738397]">
        NOT RUN
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 font-sans text-[12px] text-[#738397]">
      AWAITING RUN
    </span>
  );
};