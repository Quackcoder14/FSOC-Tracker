import React from "react";

interface SparklineProps {
  title: string;
  data: number[];
  color: string;
  unit: string;
  minVal?: number;
  maxVal?: number;
  currentVal?: number | string;
  refLine?: number;   // Optional reference/threshold line value
  refColor?: string;
}

export const SparklineChart: React.FC<SparklineProps> = ({
  title,
  data,
  color,
  unit,
  minVal,
  maxVal,
  currentVal,
  refLine,
  refColor = "rgba(115, 131, 151, 0.4)",
}) => {
  const W = 300;
  const H = 52;
  const PX = 6;
  const PY = 6;

  const points = data.slice(-HISTORY_POINTS);
  const min = minVal !== undefined ? minVal : Math.min(...points, 0);
  const max = maxVal !== undefined ? maxVal : Math.max(...points, 1);
  const range = max - min || 1;

  const toXY = (val: number, idx: number): [number, number] => {
    const x = PX + (idx / Math.max(points.length - 1, 1)) * (W - 2 * PX);
    const y = H - PY - ((val - min) / range) * (H - 2 * PY);
    return [x, y];
  };

  const pathData = points
    .map((val, idx) => {
      const [x, y] = toXY(val, idx);
      return `${idx === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");

  const latest =
    currentVal !== undefined
      ? currentVal
      : points.length > 0
      ? points[points.length - 1].toFixed(2)
      : "—";

  // Reference line Y position
  const refY =
    refLine !== undefined
      ? H - PY - ((Math.max(min, Math.min(max, refLine)) - min) / range) * (H - 2 * PY)
      : null;

  return (
    <div className="bg-[#111A28] border border-[#26364A] rounded-md p-3 flex flex-col gap-1.5">
      <div className="flex justify-between items-baseline">
        <span className="font-sans font-medium text-[11px] uppercase tracking-[0.05em] text-[#738397]">
          {title}
        </span>
        <span className="font-mono text-[13px] font-medium text-[#E8EDF3]">
          {latest}
          <span className="text-[11px] text-[#738397] font-normal ml-1">{unit}</span>
        </span>
      </div>

      <div className="w-full relative" style={{ height: H }}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full h-full overflow-visible"
          aria-hidden="true"
        >
          {/* Gridlines — very subtle */}
          {[0.25, 0.5, 0.75].map((t) => {
            const y = PY + (1 - t) * (H - 2 * PY);
            return (
              <line
                key={t}
                x1={PX}
                y1={y}
                x2={W - PX}
                y2={y}
                stroke="rgba(38, 54, 74, 0.5)"
                strokeWidth={0.5}
              />
            );
          })}

          {/* Zero line if crosses */}
          {min < 0 && max > 0 && (
            <line
              x1={PX}
              y1={H - PY - ((0 - min) / range) * (H - 2 * PY)}
              x2={W - PX}
              y2={H - PY - ((0 - min) / range) * (H - 2 * PY)}
              stroke="rgba(115, 131, 151, 0.35)"
              strokeWidth={0.5}
              strokeDasharray="2,2"
            />
          )}

          {/* Reference threshold line */}
          {refY !== null && (
            <line
              x1={PX}
              y1={refY}
              x2={W - PX}
              y2={refY}
              stroke={refColor}
              strokeWidth={1}
              strokeDasharray="3,3"
            />
          )}

          {/* Data line */}
          {points.length > 1 && (
            <path
              d={pathData}
              fill="none"
              stroke={color}
              strokeWidth={1.5}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Latest value dot */}
          {points.length > 0 && (() => {
            const [lx, ly] = toXY(points[points.length - 1], points.length - 1);
            return (
              <circle cx={lx} cy={ly} r={2.5} fill={color} />
            );
          })()}
        </svg>
      </div>
    </div>
  );
};

const HISTORY_POINTS = 60;

interface TelemetryChartsProps {
  history: {
    error_x: number[];
    error_y: number[];
    rmse: number[];
    pan_cmd: number[];
    tilt_cmd: number[];
    latency: number[];
  };
}

export const TelemetryChartsGrid: React.FC<TelemetryChartsProps> = ({ history }) => {
  const rmse = history.rmse;
  const errX = history.error_x;
  const panCmd = history.pan_cmd;
  const latency = history.latency;

  const currentRmse = rmse.length > 0 ? rmse[rmse.length - 1] : undefined;
  const currentErrX = errX.length > 0 ? errX[errX.length - 1] : undefined;
  const currentPan = panCmd.length > 0 ? panCmd[panCmd.length - 1] : undefined;
  const currentLat = latency.length > 0 ? latency[latency.length - 1] : undefined;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <SparklineChart
        title="Tracking RMSE"
        data={rmse}
        color="#F28C28"
        unit="px"
        minVal={0}
        refLine={10}
        refColor="rgba(217, 83, 79, 0.35)"
        currentVal={currentRmse !== undefined ? currentRmse.toFixed(2) : undefined}
      />
      <SparklineChart
        title="Image Error X"
        data={errX}
        color="#1F78B4"
        unit="px"
        currentVal={currentErrX !== undefined ? currentErrX.toFixed(2) : undefined}
      />
      <SparklineChart
        title="Pan Command"
        data={panCmd}
        color="#AAB7C5"
        unit="°/s"
        currentVal={currentPan !== undefined ? currentPan.toFixed(3) : undefined}
      />
      <SparklineChart
        title="Frame Latency"
        data={latency}
        color="#4B93C3"
        unit="ms"
        minVal={0}
        refLine={50}
        refColor="rgba(217, 154, 36, 0.35)"
        currentVal={currentLat !== undefined ? currentLat.toFixed(1) : undefined}
      />
    </div>
  );
};
