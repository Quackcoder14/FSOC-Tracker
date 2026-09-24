import { useState, useEffect, useCallback, useRef } from "react";
import { Vector3, Euler } from "three";
import { Maximize2, Minimize2 } from "lucide-react";
import { WorldSceneWrapper } from "./WorldScene";
import { WorldTelemetryPanel } from "./WorldTelemetry";
import { WorldTelemetry, WorldViewState, ViewerCameraState, DEFAULT_VIEWER_CAMERA_STATE, WORLD_VIEW_CONSTANTS } from "./worldViewTypes";
import { TrackingState } from "../types/telemetry";

interface WorldViewProps {
  telemetry: import("../types/telemetry").TelemetryPacket | null;
  className?: string;
}

export function WorldView({ telemetry, className = "" }: WorldViewProps) {
  const [worldState, setWorldState] = useState<WorldViewState | null>(null);
  const [viewerCamera, setViewerCamera] = useState<ViewerCameraState>(DEFAULT_VIEWER_CAMERA_STATE);
  const [showTrajectory, setShowTrajectory] = useState(true);
  const [showErrorArc, setShowErrorArc] = useState(true);
  const [showAxes, setShowAxes] = useState(true);
  const [followMode, setFollowMode] = useState<"fixed" | "follow_camera" | "follow_target">("fixed");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const trajectoryPointsRef = useRef<Vector3[]>([]);
  const lastTelemetryRef = useRef<WorldTelemetry | null>(null);

  // Convert telemetry to world state
  useEffect(() => {
    if (!telemetry?.world) return;

    const w = telemetry.world;
    const {
      target_position,
      camera_position,
      camera_pan_deg,
      camera_tilt_deg,
      boresight_direction,
      hfov_deg,
      vfov_deg,
      target_distance,
    } = w;

    // Three.js uses right-handed coordinates: +X right, +Y up, +Z out of screen
    // Our world: +X right, +Y up, +Z forward (along initial boresight)
    // So we can use the coordinates directly
    const targetPos = new Vector3(target_position[0], target_position[1], target_position[2]);
    const camPos = new Vector3(camera_position[0], camera_position[1], camera_position[2]);
    const boresightDir = new Vector3(boresight_direction[0], boresight_direction[1], boresight_direction[2]);

    // Camera rotation: pan around Y, tilt around X
    // Note: positive pan = camera rotates right = boresight points left in world
    // So the camera's local -Z axis points along boresight
    const camRotation = new Euler(
      -camera_tilt_deg * Math.PI / 180, // tilt around X (negative because camera tilt up = boresight down)
      -camera_pan_deg * Math.PI / 180,  // pan around Y (negative because camera pan right = boresight left)
      0,
      "YXZ"
    );

    setWorldState({
      targetPosition: targetPos,
      cameraPosition: camPos,
      cameraRotation: camRotation,
      boresightDirection: boresightDir,
      hfovDeg: hfov_deg,
      vfovDeg: vfov_deg,
      targetDistance: target_distance,
    });

    lastTelemetryRef.current = w;

    // Update trajectory trail
    trajectoryPointsRef.current.push(targetPos.clone());
    if (trajectoryPointsRef.current.length > WORLD_VIEW_CONSTANTS.trajectoryMaxPoints) {
      trajectoryPointsRef.current.shift();
    }
  }, [telemetry?.world]);

  // Handle follow modes
  useEffect(() => {
    if (!worldState || followMode === "fixed") return;

    const updateCamera = () => {
      if (followMode === "follow_camera") {
        // Camera follows the simulated camera position but maintains offset
        const camPos = worldState.cameraPosition.clone();
        const targetPos = worldState.targetPosition.clone();
        const center = new Vector3().addVectors(camPos, targetPos).multiplyScalar(0.5);
        const distance = camPos.distanceTo(targetPos);
        const frameDistance = Math.max(distance * 1.5, 8);

        setViewerCamera(prev => ({
          ...prev,
          target: center,
          position: new Vector3(center.x, center.y + frameDistance * 0.5, center.z + frameDistance),
        }));
      } else if (followMode === "follow_target") {
        // Camera follows the target
        const targetPos = worldState.targetPosition.clone();
        setViewerCamera(prev => ({
          ...prev,
          target: targetPos,
          position: new Vector3(targetPos.x, targetPos.y + 8, targetPos.z + 15),
        }));
      }
    };

    updateCamera();
  }, [worldState, followMode]);

  const handleResetView = useCallback(() => {
    if (!worldState) return;
    const targetPos = worldState.targetPosition.clone();
    const camPos = worldState.cameraPosition.clone();
    const center = new Vector3().addVectors(targetPos, camPos).multiplyScalar(0.5);
    const distance = targetPos.distanceTo(camPos);
    const frameDistance = Math.max(distance * 1.5, 8);

    setViewerCamera({
      position: new Vector3(center.x, center.y + frameDistance * 0.5, center.z + frameDistance),
      target: center,
      mode: "fixed",
    });
    setFollowMode("fixed");
  }, [worldState]);

  const trackingState = telemetry?.tracking?.state as TrackingState | undefined;

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
    <div className={`flex flex-col h-full ${className}`}>
      {/* World View Header */}
      <div className="flex flex-shrink-0 flex-col border-b border-[#26364A] bg-[#0B111B]">
        <div className="flex items-center justify-between px-5 py-2">
          <div className="flex items-center gap-4">
            <span className="section-label">World View</span>
            <span className="font-sans text-[10px] text-[#738397] uppercase tracking-wide whitespace-nowrap">
              External Simulation Geometry
            </span>
          </div>
        </div>
        
        <div className="flex items-center justify-between px-5 pb-2 gap-3 overflow-x-auto">
          {/* View options */}
          <div className="flex items-center gap-1.5 bg-[#111A28] rounded border border-[#26364A] p-1 flex-shrink-0">
            <button
              onClick={() => setFollowMode("fixed")}
              className={`px-3 py-1.5 rounded text-[10px] font-mono transition-colors whitespace-nowrap ${
                followMode === "fixed"
                  ? "bg-[#1F78B4] text-[#E8EDF3]"
                  : "text-[#738397] hover:text-[#AAB7C5]"
              }`}
              title="Fixed observer view"
            >
              FIXED
            </button>
            <button
              onClick={() => setFollowMode("follow_camera")}
              className={`px-3 py-1.5 rounded text-[10px] font-mono transition-colors whitespace-nowrap ${
                followMode === "follow_camera"
                  ? "bg-[#1F78B4] text-[#E8EDF3]"
                  : "text-[#738397] hover:text-[#AAB7C5]"
              }`}
              title="Follow simulated camera"
            >
              FOLLOW CAM
            </button>
            <button
              onClick={() => setFollowMode("follow_target")}
              className={`px-3 py-1.5 rounded text-[10px] font-mono transition-colors whitespace-nowrap ${
                followMode === "follow_target"
                  ? "bg-[#1F78B4] text-[#E8EDF3]"
                  : "text-[#738397] hover:text-[#AAB7C5]"
              }`}
              title="Follow target"
            >
              FOLLOW TGT
            </button>
          </div>

          <button
            onClick={handleResetView}
            className="px-3 py-1.5 rounded text-[10px] font-mono bg-[#111A28] border border-[#26364A] text-[#738397] hover:text-[#AAB7C5] hover:border-[#34475E] transition-colors whitespace-nowrap flex-shrink-0"
            title="Reset view"
          >
            RESET VIEW
          </button>

          <div className="flex items-center gap-3 border-l border-[#26364A] pl-3 flex-shrink-0">
            <label className="flex items-center gap-2 text-[10px] text-[#738397] cursor-pointer whitespace-nowrap">
              <input
                type="checkbox"
                checked={showTrajectory}
                onChange={(e) => setShowTrajectory(e.target.checked)}
                className="rounded border-[#26364A] bg-[#070B12] text-[#1F78B4] focus:ring-0"
              />
              TRAIL
            </label>
            <label className="flex items-center gap-2 text-[10px] text-[#738397] cursor-pointer whitespace-nowrap">
              <input
                type="checkbox"
                checked={showErrorArc}
                onChange={(e) => setShowErrorArc(e.target.checked)}
                className="rounded border-[#26364A] bg-[#070B12] text-[#1F78B4] focus:ring-0"
              />
              ERROR
            </label>
            <label className="flex items-center gap-2 text-[10px] text-[#738397] cursor-pointer whitespace-nowrap">
              <input
                type="checkbox"
                checked={showAxes}
                onChange={(e) => setShowAxes(e.target.checked)}
                className="rounded border-[#26364A] bg-[#070B12] text-[#1F78B4] focus:ring-0"
              />
              AXES
            </label>
          </div>
        </div>
      </div>

      {/* 3D Scene */}
      <div ref={containerRef} className="flex-1 min-h-0 relative bg-[#070B12] rounded border border-[#1A2839] overflow-hidden">
        {/* Fullscreen Button */}
        <button
          onClick={toggleFullscreen}
          className="absolute top-2 right-2 z-10 p-2 rounded bg-[#111A28] border border-[#26364A] text-[#738397] hover:text-[#E8EDF3] hover:border-[#34475E] hover:bg-[#162133] transition-colors"
          title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
        >
          {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
        </button>
        {worldState ? (
          <WorldSceneWrapper
            worldState={worldState}
            viewerCamera={viewerCamera}
            setViewerCamera={setViewerCamera}
            showTrajectory={showTrajectory}
            trajectoryPoints={trajectoryPointsRef.current}
            showErrorArc={showErrorArc}
            showAxes={showAxes}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-[#738397]">
            <div className="text-center">
              <div className="font-mono text-[12px] mb-2">WAITING FOR WORLD TELEMETRY</div>
              <div className="font-sans text-[11px]">Start simulation to see 3D geometry</div>
            </div>
          </div>
        )}
      </div>

      {/* World Telemetry Panel */}
      <div className="flex-shrink-0 p-4 border-t border-[#26364A] bg-[#0B111B] max-h-64 overflow-y-auto">
        <WorldTelemetryPanel world={lastTelemetryRef.current} trackingState={trackingState} />
      </div>
    </div>
  );
}