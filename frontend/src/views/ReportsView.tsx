import React, { useState, useEffect, useCallback } from "react";
import { wsService } from "../services/websocket";
import { ControlButton } from "../components/ui/ControlButton";
import { SectionHeader, PageHeader } from "../components/ui/SectionHeader";
import { PanelSection } from "../components/ui/PanelSection";
import { StatusBadge } from "../components/ui/StatusBadge";
import { MetricRow } from "../components/ui/MetricRow";
import { Download, FileText, CheckCircle2, AlertCircle, ExternalLink } from "lucide-react";
import { BenchmarkStatus, BenchmarkState } from "../services/websocket";

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
  acquisitionTime?: number | null;
  reacquisitionTime?: number | null;
}

interface ReportsViewProps {
  runs: RunRecord[];
  setRuns: React.Dispatch<React.SetStateAction<RunRecord[]>>;
}

export const ReportsView: React.FC<ReportsViewProps> = ({ runs, setRuns }) => {
  const [reportInfo, setReportInfo] = useState<{ html_path?: string; json_path?: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedRun, setSelectedRun] = useState<RunRecord | null>(null);
  const [benchmarkStatus, setBenchmarkStatus] = useState<BenchmarkStatus | null>(null);

  useEffect(() => {
    const unsub = wsService.onReport((data) => {
      setReportInfo(data);
      setLoading(false);
    });
    return unsub;
  }, []);

  // Track live benchmark metrics for display (not for run tracking - that's in App)
  useEffect(() => {
    const unsubBenchmark = wsService.onBenchmarkStatus((status) => {
      setBenchmarkStatus(status);
    });
    return unsubBenchmark;
  }, []);

  const handleGenerate = useCallback(() => {
    setLoading(true);
    wsService.generateReport();
  }, []);

  const handleDownloadReport = useCallback(() => {
    // Download all runs as CSV
    if (runs.length === 0) return;

    const headers = ["Run ID", "Mode", "Timestamp", "Frames Processed", "RMSE (px)", "Lock Retention (%)", "Throughput (FPS)", "Latency (ms)", "Status"];
    const rows = runs.map(run => [
      run.id,
      run.mode,
      run.timestamp,
      String(run.framesProcessed ?? ""),
      String(run.rmse?.toFixed(3) ?? ""),
      String(run.lock?.toFixed(2) ?? ""),
      String(run.fps?.toFixed(2) ?? ""),
      String(run.latency?.toFixed(2) ?? ""),
      run.status
    ]);

    const csv = [headers, ...rows].map(row => row.map(cell => `"${cell}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `fsoc_tracker_runs_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [runs]);

  const handleSelectRun = useCallback((run: RunRecord) => {
    setSelectedRun((prev) => (prev?.id === run.id ? null : run));
  }, []);

  const handleExportRun = useCallback((run: RunRecord) => {
    const rows = [
      ["Metric", "Value", "Unit"],
      ["Run ID", run.id, ""],
      ["Mode", run.mode, ""],
      ["Timestamp", run.timestamp, ""],
      ["RMSE", run.rmse?.toFixed(3) ?? "", "px"],
      ["Lock Retention", run.lock?.toFixed(2) ?? "", "%"],
      ["Throughput", run.fps?.toFixed(2) ?? "", "FPS"],
      ["P95 Latency", run.latency?.toFixed(2) ?? "", "ms"],
      ["Frames Processed", String(run.framesProcessed ?? ""), ""],
      ["Status", run.status, ""],
    ];
    const csv = rows.map((r) => r.map((c) => `"${c}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `run_${run.id}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, []);

  return (
    <div className="flex flex-col h-full min-h-0 bg-[#070B12] selectable">
      {/* Header */}
      <div className="flex-shrink-0 p-4 border-b border-[#26364A] bg-[#0B111B]">
        <PageHeader
          title="Results"
          subtitle="Run history, evaluation records, and report generation."
          action={
            <ControlButton
              variant="primary"
              icon={<Download />}
              onClick={handleDownloadReport}
              disabled={runs.length === 0}
            >
              DOWNLOAD REPORT
            </ControlButton>
          }
        />
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4 max-w-5xl mx-auto w-full">

        {/* Report ready notification */}
        {reportInfo && (
          <PanelSection level={1} padding="sm">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="w-4 h-4 text-[#38A169] flex-shrink-0 mt-0.5" />
              <div className="space-y-1.5">
                <span className="font-sans font-semibold text-[12px] text-[#38A169]">REPORT READY</span>
                <div className="space-y-0.5">
                  <div className="flex gap-2">
                    <span className="font-sans text-[11px] text-[#738397]">HTML:</span>
                    <span className="font-mono text-[11px] text-[#4B93C3] select-all break-all">{reportInfo.html_path}</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="font-sans text-[11px] text-[#738397]">JSON:</span>
                    <span className="font-mono text-[11px] text-[#4B93C3] select-all break-all">{reportInfo.json_path}</span>
                  </div>
                </div>
              </div>
            </div>
          </PanelSection>
        )}

        {/* Current Run - Live Benchmark Metrics */}
        {benchmarkStatus && benchmarkStatus.state === "running" && (
          <PanelSection level={1} padding="md">
            <SectionHeader title="Current Run" className="mb-3" />
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <MetricRow label="Frames Processed" value={benchmarkStatus.framesProcessed ?? "—"} />
              <MetricRow label="Frames Evaluated" value={benchmarkStatus.framesEvaluated ?? "—"} />
              <MetricRow label="Running RMSE" value={benchmarkStatus.currentRmse !== undefined ? benchmarkStatus.currentRmse.toFixed(2) : "—"} unit="px" />
              <MetricRow label="Lock Retention" value={benchmarkStatus.currentLockRetention !== undefined ? benchmarkStatus.currentLockRetention.toFixed(1) : "—"} unit="%" />
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <MetricRow label="Engine FPS" value={benchmarkStatus.currentFps?.toFixed(1)} unit="FPS" />
              <MetricRow label="P95 Latency" value={benchmarkStatus.currentLatency !== undefined ? benchmarkStatus.currentLatency.toFixed(1) : "—"} unit="ms" />
            </div>
            <div className="flex items-center justify-between pt-3 border-t border-[#1B2839]">
              <span className="font-sans text-[11px] text-[#738397] uppercase tracking-wide">STATUS</span>
              <span className="inline-flex items-center gap-1.5 font-sans font-medium text-[12px] text-[#1F78B4]">
                <span className="status-dot bg-[#1F78B4]" /> RUNNING
              </span>
            </div>
          </PanelSection>
        )}

        {/* Recent Runs table */}
        <PanelSection level={1} padding="none">
          <div className="px-4 pt-4 pb-2">
            <SectionHeader
              title="Recent Runs"
              action={
                <span className="font-sans text-[11px] text-[#738397]">
                  {`${runs.length} records`}
                </span>
              }
            />
          </div>

          {runs.length === 0 ? (
            <div className="px-4 py-12 text-center">
              <AlertCircle className="w-12 h-12 text-[#738397] mx-auto mb-4" />
              <h3 className="font-sans text-[14px] text-[#E8EDF3] mb-2">No Run History</h3>
              <p className="font-sans text-[12px] text-[#738397] leading-relaxed">
                No benchmark or simulation runs recorded yet.<br />
                Run a benchmark or simulation to generate results.
              </p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse" role="table" aria-label="Run history">
                  <thead>
                    <tr className="border-b border-[#26364A]">
                      {[
                        { label: "Run ID",      align: "left" },
                        { label: "Mode",        align: "left" },
                        { label: "Timestamp",   align: "left" },
                        { label: "Frames",      align: "right" },
                        { label: "RMSE",        align: "right" },
                        { label: "Lock",        align: "right" },
                        { label: "Throughput",  align: "right" },
                        { label: "Latency",     align: "right" },
                        { label: "Status",      align: "right" },
                      ].map(({ label, align }) => (
                        <th
                          key={label}
                          className={`px-4 py-2.5 font-sans font-medium text-[11px] uppercase tracking-[0.05em] text-[#738397] text-${align}`}
                        >
                          {label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run, idx) => (
                      <tr
                        key={run.id}
                        className={`border-b border-[#1B2839] hover:bg-[#0f1926] transition-colors duration-100 cursor-pointer ${
                          idx % 2 === 0 ? "bg-[#0f1724]" : ""
                        }${selectedRun?.id === run.id ? " bg-[#153040]" : ""}`}
                        tabIndex={0}
                        onClick={() => handleSelectRun(run)}
                        aria-label={`Run ${run.id}, ${run.status}`}
                      >
                        <td className="px-4 py-2.5 font-mono text-[12px] font-medium text-[#F28C28] selectable">
                          {run.id}
                        </td>
                        <td className="px-4 py-2.5 font-sans text-[12px] text-[#AAB7C5] selectable">
                          {run.mode}
                        </td>
                        <td className="px-4 py-2.5 font-mono text-[11px] text-[#738397] selectable">
                          {run.timestamp}
                        </td>
                        <td className="px-4 py-2.5 font-mono text-[12px] text-[#E8EDF3] text-right selectable">
                          {run.framesProcessed !== undefined ? String(run.framesProcessed) : "—"}
                        </td>
                        <td className="px-4 py-2.5 font-mono text-[12px] text-[#E8EDF3] text-right selectable">
                          {run.rmse !== null ? `${run.rmse.toFixed(2)} px` : "—"}
                        </td>
                        <td className="px-4 py-2.5 font-mono text-[12px] text-[#E8EDF3] text-right selectable">
                          {run.lock !== null ? `${run.lock.toFixed(1)} %` : "—"}
                        </td>
                        <td className="px-4 py-2.5 font-mono text-[12px] text-[#E8EDF3] text-right selectable">
                          {run.fps !== null ? `${run.fps.toFixed(1)} FPS` : "—"}
                        </td>
                        <td className="px-4 py-2.5 font-mono text-[12px] text-[#E8EDF3] text-right selectable">
                          {run.latency !== null ? `${run.latency.toFixed(1)} ms` : "—"}
                        </td>
                        <td className="px-4 py-2.5 text-right pr-4">
                          <StatusBadge
                            variant={run.status === "pass" ? "pass" : run.status === "fail" ? "fail" : run.status === "complete" ? "track" : "idle"}
                            className="text-[11px]"
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Selected run details */}
              {selectedRun && (
                <div className="mt-4 p-4 bg-[#111A28] border border-[#26364A] rounded-md">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-sans font-semibold text-[13px] text-[#E8EDF3]">Run Details — {selectedRun.id}</h4>
                    <div className="flex items-center gap-2">
                      <ControlButton
                        variant="secondary"
                        size="sm"
                        icon={<Download />}
                        onClick={() => handleExportRun(selectedRun)}
                      >
                        EXPORT
                      </ControlButton>
                      <ControlButton variant="tertiary" size="sm" onClick={() => setSelectedRun(null)}>CLOSE</ControlButton>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <MetricRow label="Frames Processed" value={selectedRun.framesProcessed ?? "—"} />
                    <MetricRow label="Frames Evaluated" value={selectedRun.framesEvaluated ?? "—"} />
                    <MetricRow label="RMSE" value={selectedRun.rmse !== null ? selectedRun.rmse.toFixed(2) : "—"} unit="px" />
                    <MetricRow label="Lock Ret." value={selectedRun.lock !== null ? selectedRun.lock.toFixed(1) : "—"} unit="%" />
                    <MetricRow label="Throughput" value={selectedRun.fps !== null ? selectedRun.fps.toFixed(1) : "—"} unit="FPS" />
                    <MetricRow label="P95 Latency" value={selectedRun.latency !== null ? selectedRun.latency.toFixed(1) : "—"} unit="ms" />
                    <MetricRow label="Acquisition Time" value={selectedRun.acquisitionTime !== null ? selectedRun.acquisitionTime.toFixed(1) : "—"} unit="ms" />
                    <MetricRow label="Reacquisition Time" value={selectedRun.reacquisitionTime !== null ? selectedRun.reacquisitionTime.toFixed(1) : "—"} unit="ms" />
                  </div>
                </div>
              )}
            </>
          )}
        </PanelSection>

        {/* Report path display */}
          {reportInfo && (
            <PanelSection level={1} padding="sm">
              <SectionHeader title="Report Deliverables" className="mb-3" />
              <div className="space-y-2">
                {reportInfo.html_path && (
                  <div className="flex items-center gap-2">
                    <FileText className="w-3.5 h-3.5 text-[#738397] flex-shrink-0" />
                    <span className="font-sans text-[11px] text-[#738397]">HTML:</span>
                    <span className="font-mono text-[11px] text-[#4B93C3] select-all break-all">{reportInfo.html_path}</span>
                  </div>
                )}
                {reportInfo.json_path && (
                  <div className="flex items-center gap-2">
                    <FileText className="w-3.5 h-3.5 text-[#738397] flex-shrink-0" />
                    <span className="font-sans text-[11px] text-[#738397]">JSON:</span>
                    <span className="font-mono text-[11px] text-[#4B93C3] select-all break-all">{reportInfo.json_path}</span>
                  </div>
                )}
              </div>
              <ul className="mt-3 pt-3 border-t border-[#1B2839] space-y-1.5">
                {[
                  "Full mathematical error convergence statistics (RMSE, Mean, Median, Max)",
                  "Tracking state transitions and lock retention timeline",
                  "Subsystem parameter snapshot (Camera, Kalman Q/R, PID coefficients)",
                  "Execution throughput and latency percentiles (P50, P95, P99)",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-2">
                    <FileText className="w-3.5 h-3.5 text-[#738397] flex-shrink-0 mt-0.5" />
                    <span className="font-sans text-[12px] text-[#AAB7C5]">{item}</span>
                  </li>
                ))}
              </ul>
            </PanelSection>
          )}
      </div>
    </div>
  );
};

export default ReportsView;