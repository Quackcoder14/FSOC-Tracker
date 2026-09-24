import React from "react";
import { TelemetryPacket } from "../types/telemetry";
import { SectionHeader, PageHeader } from "../components/ui/SectionHeader";
import { PanelSection } from "../components/ui/PanelSection";
import { StatusBadge, trackingStateToVariant } from "../components/ui/StatusBadge";
import { MetricRow } from "../components/ui/MetricRow";

interface ScientificDebugViewProps {
  telemetry: TelemetryPacket | null;
}

export const ScientificDebugView: React.FC<ScientificDebugViewProps> = ({ telemetry }) => {
  const candidates = telemetry?.detection?.candidates ?? [];
  const tracking = telemetry?.tracking;
  const detection = telemetry?.detection;
  const control = telemetry?.control;

  const trackVariant = trackingStateToVariant(tracking?.state ?? "IDLE");

  return (
    <div className="p-4 space-y-4">
      <PageHeader
        title="Scientific View"
        subtitle="Internal state inspection — detection pipeline, Kalman filter, and beacon validation subsystem."
      />

      {/* ── Top 3-column panels ──────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">

        {/* Detection */}
        <PanelSection level={1} padding="sm">
          <SectionHeader title="Detection" className="mb-3" />
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-sans text-[12px] text-[#738397]">Beacon Lock</span>
              <StatusBadge
                variant={detection?.detected ? "track" : "idle"}
                label={detection?.detected ? "DETECTED" : "NONE"}
                className="text-[11px]"
              />
            </div>
            <MetricRow label="Candidates"  value={detection?.candidate_count ?? 0} />
            <MetricRow
              label="Confidence"
              value={detection?.confidence !== undefined ? (detection.confidence * 100).toFixed(1) : null}
              unit="%"
              valueColor={
                detection?.confidence !== undefined && detection.confidence >= 0.9
                  ? "text-[#38A169]"
                  : detection?.confidence !== undefined && detection.confidence >= 0.6
                  ? "text-[#D99A24]"
                  : "text-[#E8EDF3]"
              }
            />
            <MetricRow
              label="Centroid X"
              value={detection?.x?.toFixed(1)}
              unit="px"
            />
            <MetricRow
              label="Centroid Y"
              value={detection?.y?.toFixed(1)}
              unit="px"
            />
          </div>
        </PanelSection>

        {/* Tracker / Kalman */}
        <PanelSection level={1} padding="sm">
          <SectionHeader title="Tracker — Kalman Filter" className="mb-3" />
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-sans text-[12px] text-[#738397]">State</span>
              <StatusBadge variant={trackVariant} className="text-[11px]" />
            </div>
            <MetricRow label="Pred. X"   value={tracking?.predicted_x?.toFixed(2)} unit="px" />
            <MetricRow label="Pred. Y"   value={tracking?.predicted_y?.toFixed(2)} unit="px" />
            <MetricRow label="Meas. X"   value={tracking?.measured_x?.toFixed(2) ?? "—"} unit="px" />
            <MetricRow label="Meas. Y"   value={tracking?.measured_y?.toFixed(2) ?? "—"} unit="px" />
            <div className="border-t border-[#1B2839] pt-2 mt-1" />
            <MetricRow label="Velocity X" value={tracking?.velocity_x?.toFixed(2)} unit="px/s" />
            <MetricRow label="Velocity Y" value={tracking?.velocity_y?.toFixed(2)} unit="px/s" />
          </div>
        </PanelSection>

        {/* Beacon Validation (replaces "AI" framing) */}
        <PanelSection level={1} padding="sm">
          <SectionHeader title="Beacon Validation" className="mb-3" />
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-sans text-[12px] text-[#738397]">Classical CV</span>
              <StatusBadge variant="ready" label="READY" className="text-[11px]" />
            </div>
            <div className="flex items-center justify-between">
              <span className="font-sans text-[12px] text-[#738397]">CNN Validator</span>
              <StatusBadge variant="ready" label="READY" className="text-[11px]" />
            </div>
            <div className="flex items-center justify-between">
              <span className="font-sans text-[12px] text-[#738397]">Runtime</span>
              <span className="font-mono text-[12px] text-[#AAB7C5]">ONNX</span>
            </div>
            <MetricRow
              label="Fused Confidence"
              value={
                detection?.confidence !== undefined
                  ? detection.confidence.toFixed(3)
                  : null
              }
            />
            <div className="border-t border-[#1B2839] pt-2 mt-1" />
            <MetricRow label="Error X"    value={control?.error_x_px?.toFixed(2)} unit="px" />
            <MetricRow label="Error Y"    value={control?.error_y_px?.toFixed(2)} unit="px" />
            <MetricRow label="Pan Cmd"    value={control?.pan_cmd_deg_s?.toFixed(3)} unit="°/s" />
            <MetricRow label="Tilt Cmd"   value={control?.tilt_cmd_deg_s?.toFixed(3)} unit="°/s" />
          </div>
        </PanelSection>
      </div>

      {/* ── Candidate Extraction Table ───────────────────────────── */}
      <PanelSection level={1} padding="none">
        <div className="px-4 pt-4 pb-2 flex items-center justify-between">
          <SectionHeader title="Candidate Extraction" />
          <span className="font-sans text-[11px] text-[#738397]">
            Top {Math.min(candidates.length, 5)} scored blobs
          </span>
        </div>

        {candidates.length === 0 ? (
          <div className="px-4 pb-4">
            <p className="font-sans text-[12px] text-[#738397]">
              No beacon candidates detected in current frame.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse" role="table" aria-label="Beacon candidate scores">
              <thead>
                <tr className="border-b border-[#26364A]">
                  {[
                    { label: "Rank",        align: "left" },
                    { label: "Centroid",    align: "right" },
                    { label: "Area",        align: "right" },
                    { label: "Brightness",  align: "right" },
                    { label: "CV Score",    align: "right" },
                    { label: "CNN Score",   align: "right" },
                    { label: "Fused Score", align: "right" },
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
                {candidates.slice(0, 5).map((c, idx) => (
                  <tr
                    key={idx}
                    className={`border-b border-[#1B2839] ${
                      idx === 0 ? "bg-[#0f1c14]" : idx % 2 === 0 ? "bg-[#0f1724]" : ""
                    }`}
                  >
                    <td className="px-4 py-2.5 font-sans text-[12px] font-semibold text-[#AAB7C5]">
                      {idx === 0 ? (
                        <span className="inline-flex items-center gap-1.5">
                          <span className="status-dot bg-[#38A169]" /> #{idx + 1}
                        </span>
                      ) : (
                        `#${idx + 1}`
                      )}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[12px] text-[#E8EDF3] text-right">
                      ({c.x.toFixed(1)}, {c.y.toFixed(1)})
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[12px] text-[#AAB7C5] text-right">
                      {c.area.toFixed(0)} px²
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[12px] text-[#AAB7C5] text-right">
                      {c.brightness.toFixed(1)}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[12px] text-[#1F78B4] text-right">
                      {(c.cv_score * 100).toFixed(1)}%
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[12px] text-[#AAB7C5] text-right">
                      {c.ai_score !== null ? `${(c.ai_score * 100).toFixed(1)}%` : "BYPASS"}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[12px] font-semibold text-right pr-4"
                      style={{ color: idx === 0 ? "#38A169" : "#AAB7C5" }}
                    >
                      {(c.final_score * 100).toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </PanelSection>
    </div>
  );
};
