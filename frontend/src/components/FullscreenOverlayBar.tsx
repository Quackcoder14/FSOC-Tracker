import React from "react";
import { Minimize2 } from "lucide-react";

interface FullscreenOverlayBarProps {
  title: string;
  subtitle?: string;
  trackingState: string;
  errorPx: number;
  azError: number;
  elError: number;
  onExitFullscreen: () => void;
}

export function FullscreenOverlayBar({
  title,
  subtitle,
  trackingState,
  errorPx,
  azError,
  elError,
  onExitFullscreen,
}: FullscreenOverlayBarProps) {
  return (
    <div
      className="absolute top-0 left-0 right-0 z-20 bg-gradient-to-b from-[#0B111B] via-[#0B111B] to-transparent border-b border-[#26364A] px-4 py-2 pointer-events-none"
      style={{ height: 56 }}
    >
      <div className="flex items-center justify-between pointer-events-auto">
        <div className="flex items-center gap-4">
          <span className="font-sans font-semibold text-[14px] text-[#E8EDF3] tracking-wide">{title}</span>
          {subtitle && <span className="font-sans text-[10px] text-[#738397] uppercase tracking-wide">{subtitle}</span>}
        </div>
        <div className="flex items-center gap-6">
          {trackingState && (
            <div className="flex items-center gap-2">
              <span
                className={`status-dot ${
                  trackingState === "TRACK" ? "bg-[#38A169]" :
                  trackingState === "ACQUIRE" ? "bg-[#D99A24]" :
                  trackingState === "LOST" ? "bg-[#D9534F]" :
                  (trackingState === "PREDICT" || trackingState === "REACQUIRE") ? "bg-[#4B93C3]" :
                  "bg-[#738397]"
                }`}
              />
              <span className="font-sans font-medium text-[11px] text-[#AAB7C5]">{trackingState}</span>
            </div>
          )}
          {errorPx > 0 && (
            <span className="font-mono text-[11px] text-[#F28C28]">
              ERROR {errorPx.toFixed(1)} PX
            </span>
          )}
          {(azError !== 0 || elError !== 0) && (
            <span className="font-mono text-[11px] text-[#AAB7C5]">
              AZ {azError >= 0 ? "+" : ""}{azError.toFixed(2)}°
              EL {elError >= 0 ? "+" : ""}{elError.toFixed(2)}°
            </span>
          )}
          <button
            onClick={onExitFullscreen}
            className="flex items-center gap-1.5 px-3 py-1 rounded border border-[#26364A] bg-[#111A28] text-[#738397] font-sans text-[10px] font-medium hover:bg-[#162133] hover:border-[#34475E] transition-colors pointer-events-auto"
            aria-label="Exit fullscreen"
            title="Exit fullscreen (Esc)"
          >
            <Minimize2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}