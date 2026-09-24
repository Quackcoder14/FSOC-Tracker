import React from "react";

interface MetricRowProps {
  label: string;
  value: string | number | null | undefined;
  unit?: string;
  valueColor?: string;
  className?: string;
  mono?: boolean;
}

export const MetricRow: React.FC<MetricRowProps> = ({
  label,
  value,
  unit,
  valueColor = "text-[#E8EDF3]",
  className = "",
  mono = true,
}) => {
  const displayValue = value !== null && value !== undefined ? value : "—";

  return (
    <div className={`flex items-baseline justify-between ${className}`}>
      <span className="font-sans text-[12px] text-[#738397] leading-none">{label}</span>
      <span
        className={`${mono ? "font-mono" : "font-sans"} text-[13px] font-medium ${valueColor} leading-none`}
      >
        {displayValue}
        {unit && (
          <span className="text-[11px] text-[#738397] font-normal ml-0.5">{unit}</span>
        )}
      </span>
    </div>
  );
};

interface MetricKPIProps {
  label: string;
  value: string | number | null | undefined;
  unit?: string;
  subtext?: string;
  valueColor?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export const MetricKPI: React.FC<MetricKPIProps> = ({
  label,
  value,
  unit,
  subtext,
  valueColor = "text-[#E8EDF3]",
  size = "md",
  className = "",
}) => {
  const displayValue = value !== null && value !== undefined ? value : "—";

  const valueSizes = {
    sm: "text-[20px]",
    md: "text-[24px]",
    lg: "text-[28px]",
  };

  return (
    <div className={`flex flex-col gap-0.5 ${className}`}>
      <span className="section-label">{label}</span>
      <div className="flex items-baseline gap-1">
        <span
          className={`font-mono font-semibold ${valueSizes[size]} leading-none ${valueColor}`}
        >
          {displayValue}
        </span>
        {unit && (
          <span className="font-sans text-[12px] text-[#738397]">{unit}</span>
        )}
      </div>
      {subtext && (
        <span className="font-sans text-[11px] text-[#738397] mt-0.5">{subtext}</span>
      )}
    </div>
  );
};
