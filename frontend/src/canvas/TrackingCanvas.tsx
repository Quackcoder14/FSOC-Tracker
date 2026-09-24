import React, { useEffect, useRef, useState, useCallback } from "react";
import { Maximize2, Minimize2 } from "lucide-react";
import { TelemetryPacket } from "../types/telemetry";

interface TrackingCanvasProps {
  telemetry: TelemetryPacket | null;
  width?: number;
  height?: number;
  showDebugOverlay?: boolean;
  showErrorVector?: boolean;
}

// Design tokens for canvas overlays
const TOKEN = {
  bg: "#070B12",
  grid: "rgba(26, 40, 57, 0.45)",
  crosshair: "rgba(220, 235, 250, 0.75)",   // optical axis / boresight — crisp white
  crosshairSubtle: "rgba(140, 165, 195, 0.4)",
  beacon: "#F28C28",                         // measured centroid — ISRO saffron
  beaconGlow: "rgba(242, 140, 40, 0.25)",
  prediction: "#1F78B4",                     // Kalman prediction — space blue
  groundTruth: "#D99A24",                    // GT reference — amber dashed (diagnostic only)
  errorVector: "#F28C28",                    // Orthogonal error vector
  errorVectorSubtle: "rgba(242, 140, 40, 0.6)",
  errorVectorFill: "rgba(11, 17, 27, 0.88)",
  lockRing: "#38A169",                       // stable lock — green
  acquireRing: "#D99A24",                    // acquiring — amber
  lostRing: "#D9534F",                       // lost — red
  reacquireRing: "#4B93C3",                  // reacquiring — info blue
  hudBg: "rgba(11, 17, 27, 0.88)",
  hudBorder: "rgba(38, 54, 74, 0.95)",
  hudText: "#AAB7C5",
  hudTextDim: "#738397",
  hudAccent: "#E8EDF3",
  candidatePrimary: "rgba(56, 161, 105, 0.75)",
  candidateOther: "rgba(170, 183, 197, 0.35)",
  font: '"IBM Plex Mono", "Courier New", monospace',
};

function getReticleColor(state: string): string {
  switch (state) {
    case "TRACK": return TOKEN.lockRing;
    case "ACQUIRE": return TOKEN.acquireRing;
    case "PREDICT":
    case "REACQUIRE": return TOKEN.reacquireRing;
    case "LOST": return TOKEN.lostRing;
    default: return TOKEN.crosshair;
  }
}

export const TrackingCanvas: React.FC<TrackingCanvasProps> = ({
  telemetry,
  width = 640,
  height = 480,
  showDebugOverlay = true,
  showErrorVector = true,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imageCacheRef = useRef<HTMLImageElement>(new Image());
  const containerRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

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

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // ── Background ──────────────────────────────────────────────────
    ctx.fillStyle = TOKEN.bg;
    ctx.fillRect(0, 0, width, height);

    const drawOverlays = () => {
      const cx = width / 2;
      const cy = height / 2;

      // ── Subtle dot grid ─────────────────────────────────────────
      ctx.fillStyle = TOKEN.grid;
      for (let x = 40; x < width; x += 40) {
        for (let y = 40; y < height; y += 40) {
          ctx.fillRect(x - 0.5, y - 0.5, 1, 1);
        }
      }

      // ── Fixed Optical Axis Crosshair (Image Center / Boresight) ─
      // The optical axis represents the center of the camera FOV and MUST remain stationary.
      const armLen = 28;
      const gap = 8;
      ctx.strokeStyle = TOKEN.crosshair;
      ctx.lineWidth = 1;
      ctx.setLineDash([]);
      ctx.beginPath();
      // Horizontal arm
      ctx.moveTo(cx - armLen, cy);
      ctx.lineTo(cx - gap, cy);
      ctx.moveTo(cx + gap, cy);
      ctx.lineTo(cx + armLen, cy);
      // Vertical arm
      ctx.moveTo(cx, cy - armLen);
      ctx.lineTo(cx, cy - gap);
      ctx.moveTo(cx, cy + gap);
      ctx.lineTo(cx, cy + armLen);
      ctx.stroke();

      // Corner tick marks around center gap
      const cSize = 5;
      ctx.strokeStyle = TOKEN.crosshairSubtle;
      ctx.beginPath();
      // Top-Left
      ctx.moveTo(cx - gap - cSize, cy - gap);
      ctx.lineTo(cx - gap, cy - gap);
      ctx.lineTo(cx - gap, cy - gap - cSize);
      // Top-Right
      ctx.moveTo(cx + gap + cSize, cy - gap);
      ctx.lineTo(cx + gap, cy - gap);
      ctx.lineTo(cx + gap, cy - gap - cSize);
      // Bottom-Left
      ctx.moveTo(cx - gap - cSize, cy + gap);
      ctx.lineTo(cx - gap, cy + gap);
      ctx.lineTo(cx - gap, cy + gap + cSize);
      // Bottom-Right
      ctx.moveTo(cx + gap + cSize, cy + gap);
      ctx.lineTo(cx + gap, cy + gap);
      ctx.lineTo(cx + gap, cy + gap + cSize);
      ctx.stroke();

      // Center boresight dot
      ctx.fillStyle = TOKEN.crosshair;
      ctx.beginPath();
      ctx.arc(cx, cy, 1.2, 0, Math.PI * 2);
      ctx.fill();

      // Label image center / boresight
      ctx.fillStyle = TOKEN.crosshairSubtle;
      ctx.font = `9px ${TOKEN.font}`;
      ctx.textAlign = "center";
      ctx.fillText("BORESIGHT (+)", cx, cy + armLen + 13);

      // ── No telemetry state ──────────────────────────────────────
      if (!telemetry) {
        ctx.fillStyle = "rgba(115, 131, 151, 0.6)";
        ctx.font = `11px ${TOKEN.font}`;
        ctx.textAlign = "center";
        ctx.fillText("WAITING FOR OPTICAL TELEMETRY STREAM", cx, cy + 55);
        ctx.fillStyle = "rgba(115, 131, 151, 0.35)";
        ctx.font = `10px ${TOKEN.font}`;
        ctx.fillText("ws://127.0.0.1:8765", cx, cy + 72);
        return;
      }

      const { detection, tracking, ground_truth, control, performance, frame_index } = telemetry;

      // ── 1. Ground Truth Target (DIAGNOSTIC ONLY — amber dashed) ──
      // Clearly labeled and isolated from tracking loop
      if (ground_truth && showDebugOverlay) {
        const gtx = ground_truth.target_x;
        const gty = ground_truth.target_y;

        ctx.strokeStyle = TOKEN.groundTruth;
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.arc(gtx, gty, 16, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);

        // Small center dot for GT
        ctx.fillStyle = TOKEN.groundTruth;
        ctx.beginPath();
        ctx.arc(gtx, gty, 1.5, 0, Math.PI * 2);
        ctx.fill();

        // GT badge (minimal)
        ctx.fillStyle = "rgba(217, 154, 36, 0.85)";
        ctx.font = `bold 8.5px ${TOKEN.font}`;
        ctx.textAlign = "left";
        ctx.fillText("GT", gtx + 14, gty - 4);
      }

      // ── 2. Candidate detections ──────────────────────────────────
      if (detection?.candidates && showDebugOverlay) {
        detection.candidates.forEach((cand, idx) => {
          const color = idx === 0 ? TOKEN.candidatePrimary : TOKEN.candidateOther;
          ctx.strokeStyle = color;
          ctx.lineWidth = 1;
          const boxHalf = 8;
          ctx.strokeRect(cand.x - boxHalf, cand.y - boxHalf, boxHalf * 2, boxHalf * 2);

          if (idx === 0) {
            ctx.beginPath();
            ctx.moveTo(cand.x - 3, cand.y); ctx.lineTo(cand.x + 3, cand.y);
            ctx.moveTo(cand.x, cand.y - 3); ctx.lineTo(cand.x, cand.y + 3);
            ctx.stroke();
          }

          ctx.fillStyle = color;
          ctx.font = `8px ${TOKEN.font}`;
          ctx.textAlign = "left";
          ctx.fillText(`C${idx + 1}`, cand.x + 10, cand.y + 3);
        });
      }

      // ── 3. Kalman prediction (blue diamond) ─────────────────────
      if (tracking) {
        const kx = tracking.predicted_x;
        const ky = tracking.predicted_y;
        const state = tracking.state;

        // Velocity vector
        if (Math.abs(tracking.velocity_x) > 0.4 || Math.abs(tracking.velocity_y) > 0.4) {
          ctx.strokeStyle = "rgba(31, 120, 180, 0.65)";
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(kx, ky);
          const vx = kx + tracking.velocity_x * 0.4;
          const vy = ky + tracking.velocity_y * 0.4;
          ctx.lineTo(vx, vy);
          ctx.stroke();
        }

        // Blue diamond for Kalman prediction
        const dSize = 5;
        ctx.strokeStyle = TOKEN.prediction;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(kx, ky - dSize);
        ctx.lineTo(kx + dSize, ky);
        ctx.lineTo(kx, ky + dSize);
        ctx.lineTo(kx - dSize, ky);
        ctx.closePath();
        ctx.stroke();

        // State Reticle Ring around tracked state
        const reticleColor = getReticleColor(state);
        ctx.strokeStyle = reticleColor;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(kx, ky, 20, 0, Math.PI * 2);
        ctx.stroke();

        // Corner framing brackets
        const b = 14;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        // TL
        ctx.moveTo(kx - b, ky - b + 5); ctx.lineTo(kx - b, ky - b); ctx.lineTo(kx - b + 5, ky - b);
        // TR
        ctx.moveTo(kx + b - 5, ky - b); ctx.lineTo(kx + b, ky - b); ctx.lineTo(kx + b, ky - b + 5);
        // BL
        ctx.moveTo(kx - b, ky + b - 5); ctx.lineTo(kx - b, ky + b); ctx.lineTo(kx - b + 5, ky + b);
        // BR
        ctx.moveTo(kx + b - 5, ky + b); ctx.lineTo(kx + b, ky + b); ctx.lineTo(kx + b, ky + b - 5);
        ctx.stroke();

        // State label badge
        ctx.fillStyle = reticleColor;
        ctx.font = `bold 10px ${TOKEN.font}`;
        ctx.textAlign = "left";
        ctx.fillText(state, kx + 24, ky - 5);

        if (showDebugOverlay) {
          ctx.fillStyle = TOKEN.hudTextDim;
          ctx.font = `9px ${TOKEN.font}`;
          ctx.fillText("KALMAN PRED", kx + 24, ky + 8);
        }
      }

      // ── 4. Measured Beacon Centroid (Orange dot) ─────────────────
      let targetPx: number | null = null;
      let targetPy: number | null = null;

      if (detection?.detected && detection.x !== null && detection.y !== null) {
        targetPx = detection.x;
        targetPy = detection.y;

        // Glow ring
        ctx.fillStyle = TOKEN.beaconGlow;
        ctx.beginPath();
        ctx.arc(targetPx, targetPy, 9, 0, Math.PI * 2);
        ctx.fill();

        // Orange filled core
        ctx.fillStyle = TOKEN.beacon;
        ctx.beginPath();
        ctx.arc(targetPx, targetPy, 3.5, 0, Math.PI * 2);
        ctx.fill();

        // Centroid tag
        ctx.fillStyle = TOKEN.beacon;
        ctx.font = `bold 8.5px ${TOKEN.font}`;
        ctx.textAlign = "left";
        ctx.fillText("BEACON", targetPx + 10, targetPy - 6);
      } else if (tracking) {
        // Use Kalman estimate if detection is momentarily occluded
        targetPx = tracking.predicted_x;
        targetPy = tracking.predicted_y;
      }

      // ── 5. Explicit Orthogonal Error Vector (ΔX, ΔY, AZ, EL) ─────
      // Replaces decorative tracking line with an explicit coarse-alignment error vector:
      // TARGET (tx, ty)
      //   │
      //   │  error ΔY
      //   │
      //   └────────────+ BORESIGHT (cx, cy)
      //      error ΔX
      if (showErrorVector && control && targetPx !== null && targetPy !== null) {
        const errX = control.error_x_px;
        const errY = control.error_y_px;
        const errDist = Math.hypot(errX, errY);

        if (errDist > 2.5) {
          ctx.save();

          // 1. Direct line of sight (soft dashed)
          ctx.strokeStyle = "rgba(242, 140, 40, 0.25)";
          ctx.lineWidth = 1;
          ctx.setLineDash([2, 4]);
          ctx.beginPath();
          ctx.moveTo(cx, cy);
          ctx.lineTo(targetPx, targetPy);
          ctx.stroke();

          // 2. Orthogonal Error Path: (cx, cy) -> (targetPx, cy) -> (targetPx, targetPy)
          ctx.strokeStyle = TOKEN.errorVector;
          ctx.lineWidth = 1.5;
          ctx.setLineDash([]);
          ctx.beginPath();
          // Horizontal leg: from Boresight (cx, cy) along X to (targetPx, cy)
          ctx.moveTo(cx, cy);
          ctx.lineTo(targetPx, cy);
          // Vertical leg: from (targetPx, cy) along Y to (targetPx, targetPy)
          ctx.lineTo(targetPx, targetPy);
          ctx.stroke();

          // 3. Right-angle corner indicator at (targetPx, cy)
          const cornerSize = 7;
          const sx = targetPx > cx ? -1 : 1;
          const sy = targetPy > cy ? -1 : 1;
          ctx.strokeStyle = "rgba(242, 140, 40, 0.7)";
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(targetPx + sx * cornerSize, cy);
          ctx.lineTo(targetPx + sx * cornerSize, cy + sy * cornerSize);
          ctx.lineTo(targetPx, cy + sy * cornerSize);
          ctx.stroke();

          // 4. Direction arrow on the vertical leg pointing toward target
          const arrLen = 5;
          const arrowDir = targetPy > cy ? 1 : -1;
          ctx.fillStyle = TOKEN.errorVector;
          ctx.beginPath();
          ctx.moveTo(targetPx, targetPy);
          ctx.lineTo(targetPx - arrLen * 0.7, targetPy - arrowDir * arrLen);
          ctx.lineTo(targetPx + arrLen * 0.7, targetPy - arrowDir * arrLen);
          ctx.closePath();
          ctx.fill();

          // 5. Numerical Error Callout Box:
          //    IMAGE ERROR
          //    ΔX  +109.0 px
          //    ΔY   -59.0 px
          //    ANGULAR ERROR
          //    AZ   +0.68°
          //    EL   -0.37°
          // Place callout near midpoint of horizontal or vertical leg, clamped within bounds
          const boxW = 126;
          const boxH = 76;
          let boxX = targetPx > cx ? cx + 18 : cx - boxW - 18;
          let boxY = (cy + targetPy) / 2 - boxH / 2;

          // Clamp within canvas boundaries
          boxX = Math.max(10, Math.min(width - boxW - 10, boxX));
          boxY = Math.max(10, Math.min(height - boxH - 10, boxY));

          ctx.fillStyle = TOKEN.hudBg;
          ctx.beginPath();
          ctx.roundRect(boxX, boxY, boxW, boxH, 4);
          ctx.fill();
          ctx.strokeStyle = "rgba(242, 140, 40, 0.5)";
          ctx.lineWidth = 1;
          ctx.stroke();

          // Content inside Error Callout
          ctx.textAlign = "left";

          // Header 1: IMAGE ERROR
          ctx.fillStyle = TOKEN.hudTextDim;
          ctx.font = `bold 8px ${TOKEN.font}`;
          ctx.fillText("IMAGE ERROR", boxX + 8, boxY + 12);

          const signX = errX >= 0 ? "+" : "";
          const signY = errY >= 0 ? "+" : "";
          ctx.fillStyle = TOKEN.hudAccent;
          ctx.font = `9px ${TOKEN.font}`;
          ctx.fillText(`ΔX  ${signX}${errX.toFixed(1)} px`, boxX + 8, boxY + 24);
          ctx.fillText(`ΔY  ${signY}${errY.toFixed(1)} px`, boxX + 8, boxY + 36);

          // Divider
          ctx.strokeStyle = "rgba(38, 54, 74, 0.6)";
          ctx.beginPath();
          ctx.moveTo(boxX + 6, boxY + 41);
          ctx.lineTo(boxX + boxW - 6, boxY + 41);
          ctx.stroke();

          // Header 2: ANGULAR ERROR
          ctx.fillStyle = TOKEN.hudTextDim;
          ctx.font = `bold 8px ${TOKEN.font}`;
          ctx.fillText("ANGULAR ERROR", boxX + 8, boxY + 51);

          const az = control.error_x_deg;
          const el = control.error_y_deg;
          const signAz = az >= 0 ? "+" : "";
          const signEl = el >= 0 ? "+" : "";
          ctx.fillStyle = TOKEN.beacon;
          ctx.font = `bold 9px ${TOKEN.font}`;
          ctx.fillText(`AZ  ${signAz}${az.toFixed(2)}°`, boxX + 8, boxY + 63);
          ctx.fillText(`EL  ${signEl}${el.toFixed(2)}°`, boxX + 68, boxY + 63);

          ctx.restore();
        } else {
          // Alignment achieved indicator!
          ctx.fillStyle = "rgba(56, 161, 105, 0.9)";
          ctx.font = `bold 9px ${TOKEN.font}`;
          ctx.textAlign = "center";
          ctx.fillText("◎ BORESIGHT ALIGNED (Δ < 2.5 px)", cx, cy - armLen - 8);
        }
      }

      // ── 6. Technical Debug Overlay HUD ───────────────────────────
      // Showing: image center, camera pan, camera tilt, angular error, PID output
      if (showDebugOverlay) {
        const dbgX = 10;
        const dbgY = 10;
        const dbgW = 290;
        const dbgH = 82;

        ctx.fillStyle = TOKEN.hudBg;
        ctx.beginPath();
        ctx.roundRect(dbgX, dbgY, dbgW, dbgH, 4);
        ctx.fill();
        ctx.strokeStyle = TOKEN.hudBorder;
        ctx.lineWidth = 1;
        ctx.stroke();

        ctx.textAlign = "left";
        ctx.fillStyle = TOKEN.hudAccent;
        ctx.font = `bold 9px ${TOKEN.font}`;
        ctx.fillText("OPTICAL PAT INSTRUMENTATION", dbgX + 8, dbgY + 13);

        ctx.fillStyle = TOKEN.hudTextDim;
        ctx.font = `8.5px ${TOKEN.font}`;
        ctx.fillText(`CENTER: (X ${cx.toFixed(0)}, Y ${cy.toFixed(0)})`, dbgX + 8, dbgY + 24);

        // Divider
        ctx.strokeStyle = "rgba(38, 54, 74, 0.6)";
        ctx.beginPath();
        ctx.moveTo(dbgX + 6, dbgY + 29);
        ctx.lineTo(dbgX + dbgW - 6, dbgY + 29);
        ctx.stroke();

        // Row 1: Camera Gimbal Pan & Tilt
        const cPan = control?.camera_pan_deg ?? 0.0;
        const cTilt = control?.camera_tilt_deg ?? 0.0;
        const signCP = cPan >= 0 ? "+" : "";
        const signCT = cTilt >= 0 ? "+" : "";
        ctx.fillStyle = TOKEN.hudText;
        ctx.fillText(`CAMERA PAN  ${signCP}${cPan.toFixed(3)}°`, dbgX + 8, dbgY + 42);
        ctx.fillText(`TILT  ${signCT}${cTilt.toFixed(3)}°`, dbgX + 160, dbgY + 42);

        // Row 2: Angular Error AZ & EL
        const aAz = control?.error_x_deg ?? 0.0;
        const aEl = control?.error_y_deg ?? 0.0;
        const signAz = aAz >= 0 ? "+" : "";
        const signEl = aEl >= 0 ? "+" : "";
        ctx.fillStyle = Math.hypot(aAz, aEl) < 0.1 ? TOKEN.lockRing : TOKEN.beacon;
        ctx.fillText(`ANG ERR AZ  ${signAz}${aAz.toFixed(3)}°`, dbgX + 8, dbgY + 56);
        ctx.fillText(`EL  ${signEl}${aEl.toFixed(3)}°`, dbgX + 160, dbgY + 56);

        // Row 3: PID Velocity Command Output
        const pCmd = control?.pan_cmd_deg_s ?? 0.0;
        const tCmd = control?.tilt_cmd_deg_s ?? 0.0;
        const signPC = pCmd >= 0 ? "+" : "";
        const signTC = tCmd >= 0 ? "+" : "";
        ctx.fillStyle = TOKEN.hudTextDim;
        ctx.fillText(`PID CMD PAN ${signPC}${pCmd.toFixed(3)}°/s`, dbgX + 8, dbgY + 70);
        ctx.fillText(`TILT ${signTC}${tCmd.toFixed(3)}°/s`, dbgX + 160, dbgY + 70);
      }

      // ── 7. Performance & Frame HUD (Bottom-Left) ─────────────────
      const hudX = 10;
      const hudY = height - 52;
      const hudW = 230;
      const hudH = 42;

      ctx.fillStyle = TOKEN.hudBg;
      ctx.beginPath();
      ctx.roundRect(hudX, hudY, hudW, hudH, 4);
      ctx.fill();
      ctx.strokeStyle = TOKEN.hudBorder;
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.textAlign = "left";
      ctx.fillStyle = TOKEN.hudAccent;
      ctx.font = `bold 9px ${TOKEN.font}`;
      ctx.fillText(
        `FRAME  ${String(frame_index ?? 0).padStart(5, "0")}`,
        hudX + 8,
        hudY + 15
      );

      ctx.fillStyle = TOKEN.hudTextDim;
      ctx.font = `8.5px ${TOKEN.font}`;
      const fps = performance?.fps?.toFixed(1) ?? "—";
      const rmse = performance?.rmse_px != null ? `${performance.rmse_px.toFixed(2)} px` : "—";
      const lat = performance?.latency_ms != null ? `${performance.latency_ms.toFixed(1)} ms` : "—";
      ctx.fillText(
        `FPS ${fps}   RMSE ${rmse}   LAT ${lat}`,
        hudX + 8,
        hudY + 30
      );

      // ── 8. Timestamp & Elapsed Time (Top-Right) ──────────────────
      const tsText = `T ${(telemetry.timestamp_ms / 1000).toFixed(2)} s`;
      ctx.fillStyle = TOKEN.hudText;
      ctx.font = `9px ${TOKEN.font}`;
      ctx.textAlign = "right";
      ctx.fillText(tsText, width - 10, 18);
    };

    if (telemetry?.image_base64) {
      const img = imageCacheRef.current;
      img.onload = () => {
        ctx.drawImage(img, 0, 0, width, height);
        drawOverlays();
      };
      img.src = `data:image/jpeg;base64,${telemetry.image_base64}`;
    } else {
      drawOverlays();
    }
  }, [telemetry, width, height, showDebugOverlay, showErrorVector]);

  return (
    <div ref={containerRef} className="relative w-full h-full flex items-center justify-center overflow-hidden rounded-md border border-[#26364A] bg-[#070B12]">
      {/* Fullscreen Button */}
      <button
        onClick={toggleFullscreen}
        className="absolute top-2 right-2 z-10 p-2 rounded bg-[#111A28] border border-[#26364A] text-[#738397] hover:text-[#E8EDF3] hover:border-[#34475E] hover:bg-[#162133] transition-colors"
        title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
      >
        {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
      </button>
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        className="block max-w-full max-h-full object-contain aspect-[4/3]"
        aria-label="Optical coarse alignment viewport"
        role="img"
      />
    </div>
  );
};
