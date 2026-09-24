import React, { useEffect, useRef, useState, useCallback } from "react";
import { FullscreenOverlayBar } from "./FullscreenOverlayBar";

interface FullscreenContainerProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  telemetry?: {
    trackingState?: string;
    errorPx?: number;
    azError?: number;
    elError?: number;
  };
  className?: string;
}

export function FullscreenContainer({
  children,
  title = "VIEW",
  subtitle,
  telemetry,
  className = "",
}: FullscreenContainerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);

  const enterFullscreen = useCallback(async () => {
    if (!containerRef.current) return;
    setIsTransitioning(true);
    try {
      await containerRef.current.requestFullscreen();
      setIsFullscreen(true);
    } catch (e) {
      console.warn("Fullscreen request failed:", e);
    } finally {
      setIsTransitioning(false);
    }
  }, []);

  const exitFullscreen = useCallback(async () => {
    setIsTransitioning(true);
    try {
      await document.exitFullscreen();
      setIsFullscreen(false);
    } catch (e) {
      console.warn("Exit fullscreen failed:", e);
    } finally {
      setIsTransitioning(false);
    }
  }, []);

  useEffect(() => {
    const handleFullscreenChange = () => {
      const fs = document.fullscreenElement === containerRef.current;
      setIsFullscreen(fs);
      setIsTransitioning(false);
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isFullscreen) {
        exitFullscreen();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isFullscreen, exitFullscreen]);

  const trackingState = telemetry?.trackingState ?? "IDLE";
  const errorPx = telemetry?.errorPx ?? 0;
  const azError = telemetry?.azError ?? 0;
  const elError = telemetry?.elError ?? 0;

  return (
    <div
      ref={containerRef}
      className={`relative flex flex-col h-full min-h-0 ${className}`}
      style={{ contain: "layout style" }}
    >
      {/* Fullscreen Overlay Bar */}
      {isFullscreen && (
        <FullscreenOverlayBar
          title={title}
          subtitle={subtitle}
          trackingState={trackingState}
          errorPx={errorPx}
          azError={azError}
          elError={elError}
          onExitFullscreen={exitFullscreen}
        />
      )}

      <div className={`flex-1 min-h-0 w-full h-full flex flex-col overflow-hidden ${isFullscreen ? "fullscreen-content pt-14 bg-[#070B12]" : ""}`}>
        {children}
      </div>
    </div>
  );
}