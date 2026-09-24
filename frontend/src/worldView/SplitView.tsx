import { useState, useCallback, useEffect, useRef } from "react";
import { Maximize2, Minimize2 } from "lucide-react";
import { WorldView } from "./WorldView";
import { TrackingCanvas } from "../canvas/TrackingCanvas";
import { TelemetryPacket } from "../types/telemetry";

interface SplitViewProps {
  telemetry: TelemetryPacket | null;
}

export function SplitView({ telemetry }: SplitViewProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const toggleFullscreen = useCallback(async () => {
    if (!containerRef.current) return;
    try {
      if (!isFullscreen) {
        await containerRef.current.requestFullscreen();
        setIsFullscreen(true);
      } else {
        await document.exitFullscreen();
        setIsFullscreen(false);
      }
    } catch (e) {
      console.warn("Fullscreen toggle failed:", e);
    }
  }, [isFullscreen]);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  return (
    <div className="flex h-full min-h-0 overflow-hidden">
      {/* Left: Camera POV */}
      <div className="flex-1 min-w-0 flex flex-col p-3 gap-2 overflow-y-auto">
        <div className="flex items-center justify-between flex-shrink-0">
          <span className="section-label">Camera POV</span>
          <span className="font-mono text-[10px] text-[#738397]">OPTICAL OBSERVATION</span>
        </div>
        <div ref={containerRef} className="flex-1 min-h-0 relative flex items-center justify-center bg-[#0B111B] rounded border border-[#1A2839] p-1">
          {/* Fullscreen Button */}
          <button
            onClick={toggleFullscreen}
            className="absolute top-2 right-2 z-10 p-2 rounded bg-[#111A28] border border-[#26364A] text-[#738397] hover:text-[#E8EDF3] hover:border-[#34475E] hover:bg-[#162133] transition-colors"
            title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
          <TrackingCanvas telemetry={telemetry ?? null} />
        </div>
      </div>

      {/* Divider */}
      <div className="w-px bg-[#26364A] hidden lg:block" />

      {/* Right: World View */}
      <div className="flex-1 min-w-0 flex flex-col lg:flex-row">
        <div className="flex-1 min-w-0 lg:w-1/2 flex flex-col">
          <WorldView telemetry={telemetry} />
        </div>
      </div>
    </div>
  );
}