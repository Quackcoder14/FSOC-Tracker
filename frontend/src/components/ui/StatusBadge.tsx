import React from "react";

export type StatusVariant =
  | "track"
  | "acquire"
  | "predict"
  | "reacquire"
  | "lost"
  | "search"
  | "idle"
  | "pass"
  | "fail"
  | "warning"
  | "info"
  | "ready"
  | "processing";

interface StatusBadgeProps {
  variant: StatusVariant;
  label?: string;
  className?: string;
}

const variantMap: Record<
  StatusVariant,
  { dot: string; text: string; label: string }
> = {
  track:      { dot: "bg-[#38A169]", text: "text-[#38A169]", label: "TRACK" },
  acquire:    { dot: "bg-[#D99A24]", text: "text-[#D99A24]", label: "ACQUIRE" },
  predict:    { dot: "bg-[#4B93C3]", text: "text-[#4B93C3]", label: "PREDICT" },
  reacquire:  { dot: "bg-[#4B93C3]", text: "text-[#4B93C3]", label: "REACQUIRE" },
  lost:       { dot: "bg-[#D9534F]", text: "text-[#D9534F]", label: "LOST" },
  search:     { dot: "bg-[#738397]", text: "text-[#AAB7C5]", label: "SEARCH" },
  idle:       { dot: "bg-[#738397]", text: "text-[#738397]", label: "IDLE" },
  pass:       { dot: "bg-[#38A169]", text: "text-[#38A169]", label: "PASS" },
  fail:       { dot: "bg-[#D9534F]", text: "text-[#D9534F]", label: "FAIL" },
  warning:    { dot: "bg-[#D99A24]", text: "text-[#D99A24]", label: "WARNING" },
  info:       { dot: "bg-[#4B93C3]", text: "text-[#4B93C3]", label: "INFO" },
  ready:      { dot: "bg-[#38A169]", text: "text-[#38A169]", label: "READY" },
  processing: { dot: "bg-[#4B93C3]", text: "text-[#4B93C3]", label: "PROCESSING" },
};

export const trackingStateToVariant = (state: string): StatusVariant => {
  const map: Record<string, StatusVariant> = {
    TRACK: "track",
    ACQUIRE: "acquire",
    PREDICT: "predict",
    REACQUIRE: "reacquire",
    LOST: "lost",
    SEARCH: "search",
    IDLE: "idle",
  };
  return map[state] ?? "idle";
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  variant,
  label,
  className = "",
}) => {
  const cfg = variantMap[variant] ?? variantMap.idle;
  const displayLabel = label ?? cfg.label;

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-sans font-medium ${cfg.text} ${className}`}
      role="status"
      aria-label={displayLabel}
    >
      <span className={`status-dot ${cfg.dot}`} aria-hidden="true" />
      {displayLabel}
    </span>
  );
};
