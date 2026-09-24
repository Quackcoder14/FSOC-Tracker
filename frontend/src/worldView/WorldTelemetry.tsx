import { WorldTelemetry } from "./worldViewTypes";

interface WorldTelemetryProps {
  world: WorldTelemetry | null;
  trackingState?: string;
}

export function WorldTelemetryPanel({ world, trackingState }: WorldTelemetryProps) {
  if (!world) {
    return (
      <div className="font-sans text-[11px] text-[#738397]">
        No world telemetry available
      </div>
    );
  }

  const {
    target_position,
    camera_position,
    camera_pan_deg,
    camera_tilt_deg,
    boresight_direction,
    hfov_deg,
    vfov_deg,
    target_distance,
  } = world;

  const getStateColor = (state?: string) => {
    switch (state) {
      case "TRACK": return "#38A169";
      case "ACQUIRE": return "#D99A24";
      case "PREDICT":
      case "REACQUIRE": return "#4B93C3";
      case "LOST": return "#D9534F";
      default: return "#738397";
    }
  };

  return (
    <div className="font-sans text-[11px] space-y-3">
      <div className="font-semibold text-[#E8EDF3] border-b border-[#26364A] pb-2">
        WORLD STATE
        {trackingState && (
          <span
            className="ml-2 px-1.5 py-0.5 rounded text-[9px] font-mono"
            style={{ backgroundColor: getStateColor(trackingState) + "20", color: getStateColor(trackingState) }}
          >
            {trackingState}
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 text-[#AAB7C5]">
        <div className="font-mono">
          <span className="text-[#738397]">TARGET</span>
        </div>
        <div />
        <div>X</div>
        <div className="font-mono text-right">{target_position[0].toFixed(2)}</div>
        <div>Y</div>
        <div className="font-mono text-right">{target_position[1].toFixed(2)}</div>
        <div>Z</div>
        <div className="font-mono text-right">{target_position[2].toFixed(2)}</div>

        <div className="col-span-2 border-t border-[#1A2839] pt-1" />
        <div className="font-mono">
          <span className="text-[#738397]">CAMERA</span>
        </div>
        <div />
        <div>PAN</div>
        <div className="font-mono text-right">{camera_pan_deg >= 0 ? "+" : ""}{camera_pan_deg.toFixed(3)}°</div>
        <div>TILT</div>
        <div className="font-mono text-right">{camera_tilt_deg >= 0 ? "+" : ""}{camera_tilt_deg.toFixed(3)}°</div>

        <div className="col-span-2 border-t border-[#1A2839] pt-1" />
        <div className="font-mono">
          <span className="text-[#738397]">BORESIGHT</span>
        </div>
        <div />
        <div>X</div>
        <div className="font-mono text-right">{boresight_direction[0].toFixed(4)}</div>
        <div>Y</div>
        <div className="font-mono text-right">{boresight_direction[1].toFixed(4)}</div>
        <div>Z</div>
        <div className="font-mono text-right">{boresight_direction[2].toFixed(4)}</div>

        <div className="col-span-2 border-t border-[#1A2839] pt-1" />
        <div className="font-mono">
          <span className="text-[#738397]">FOV</span>
        </div>
        <div />
        <div>HFOV</div>
        <div className="font-mono text-right">{hfov_deg.toFixed(2)}°</div>
        <div>VFOV</div>
        <div className="font-mono text-right">{vfov_deg.toFixed(2)}°</div>

        <div className="col-span-2 border-t border-[#1A2839] pt-1" />
        <div>DISTANCE</div>
        <div className="font-mono text-right">{target_distance.toFixed(1)} m</div>
      </div>
    </div>
  );
}