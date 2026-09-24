import { useFrame, useThree, Canvas } from "@react-three/fiber";
import { useRef, useEffect, useState } from "react";
import {
  Vector3,
  Euler,
  Quaternion,
  PerspectiveCamera,
  Scene,
  AmbientLight,
  DirectionalLight,
  HemisphereLight,
  Color,
} from "three";
import { OrbitControls } from "@react-three/drei";
import { Grid } from "./Grid";
import { CameraObject } from "./CameraObject";
import { TargetObject } from "./TargetObject";
import { Boresight } from "./Boresight";
import { FOVFrustum } from "./FOVFrustum";
import { Axes } from "./Axes";
import { WorldViewState, ViewerCameraState, DEFAULT_VIEWER_CAMERA_STATE, WORLD_VIEW_CONSTANTS, WORLD_VIEW_COLORS } from "./worldViewTypes";

interface WorldSceneProps {
  worldState: WorldViewState | null;
  viewerCamera: ViewerCameraState;
  setViewerCamera: (state: ViewerCameraState) => void;
  showTrajectory?: boolean;
  trajectoryPoints?: Vector3[];
  showErrorArc?: boolean;
  showAxes?: boolean;
  onViewerCameraChange?: (position: Vector3, target: Vector3) => void;
}

export function WorldScene({
  worldState,
  viewerCamera,
  setViewerCamera,
  showTrajectory = true,
  trajectoryPoints = [],
  showErrorArc = true,
  showAxes = true,
  onViewerCameraChange,
}: WorldSceneProps) {
  const { camera: threeCamera, gl } = useThree();
  const controlsRef = useRef<any>(null);
  const [isInitialized, setIsInitialized] = useState(false);
  const autoFrameDone = useRef(false);

  // Initialize camera and controls
  useEffect(() => {
    if (!isInitialized && threeCamera) {
      threeCamera.position.copy(viewerCamera.position);
      threeCamera.lookAt(viewerCamera.target);

      if (controlsRef.current) {
        controlsRef.current.target.copy(viewerCamera.target);
        controlsRef.current.update();
      }
      setIsInitialized(true);
    }
  }, [isInitialized, threeCamera, viewerCamera]);

  // Auto-frame on first world state
  useFrame(() => {
    if (worldState && !autoFrameDone.current && controlsRef.current) {
      autoFrameDone.current = true;
      const targetPos = new Vector3().copy(worldState.targetPosition);
      const camPos = new Vector3().copy(worldState.cameraPosition);
      const center = new Vector3().addVectors(targetPos, camPos).multiplyScalar(0.5);
      const distance = targetPos.distanceTo(camPos);
      const frameDistance = Math.max(distance * 1.5, 8);

      threeCamera.position.set(center.x, center.y + frameDistance * 0.5, center.z + frameDistance);
      threeCamera.lookAt(center);
      controlsRef.current.target.copy(center);
      controlsRef.current.update();
    }
  });

  // Sync viewer camera state
  useFrame(() => {
    if (controlsRef.current && onViewerCameraChange) {
      onViewerCameraChange(threeCamera.position.clone(), controlsRef.current.target.clone());
    }
  });

  if (!worldState) {
    return (
      <>
        <ambientLight intensity={0.5} />
        <directionalLight position={[5, 10, 7]} intensity={1} />
      </>
    );
  }

  const {
    targetPosition,
    cameraPosition,
    cameraRotation,
    boresightDirection,
    hfovDeg,
    vfovDeg,
    targetDistance,
  } = worldState;

  // Convert trajectory points to array format for TargetObject
  const trailArray = trajectoryPoints.map(p => [p.x, p.y, p.z] as [number, number, number]);

  // Calculate target direction from camera to target
  const targetDir = new Vector3()
    .subVectors(targetPosition, cameraPosition)
    .normalize();

  return (
    <>
      <scene background={new Color(WORLD_VIEW_COLORS.background)}>
        {/* Lighting */}
        <ambientLight intensity={0.4} color="#8899AA" />
        <hemisphereLight groundColor="#1A2839" color="#4A5A6A" intensity={0.6} />
        <directionalLight
          position={[5, 15, 10]}
          intensity={1.2}
          color="#E8EDF3"
          castShadow
          shadow-mapSize-width={1024}
          shadow-mapSize-height={1024}
          shadow-camera-near={1}
          shadow-camera-far={50}
          shadow-camera-left={-15}
          shadow-camera-right={15}
          shadow-camera-top={15}
          shadow-camera-bottom={-15}
        />

        {/* Grid */}
        <Grid size={WORLD_VIEW_CONSTANTS.gridSize} divisions={WORLD_VIEW_CONSTANTS.gridDivisions} />

        {/* Coordinate axes */}
        {showAxes && (
          <group position={[0, 0, 0]}>
            <Axes size={3} />
          </group>
        )}

        {/* Target with trajectory trail */}
        <TargetObject
          position={targetPosition.toArray() as [number, number, number]}
          size={0.3}
          showTrail={showTrajectory}
          trailPoints={trailArray}
        />

        {/* Camera with frustum */}
        <group position={cameraPosition.toArray() as [number, number, number]}>
          <CameraObject
            position={[0, 0, 0]}
            rotation={cameraRotation.toArray() as [number, number, number]}
            hfovDeg={hfovDeg}
            vfovDeg={vfovDeg}
            targetDistance={targetDistance}
            showFrustum={true}
          />

          {/* Boresight from camera */}
          <Boresight
            direction={boresightDirection.toArray() as [number, number, number]}
            length={targetDistance * 1.1}
            showErrorArc={showErrorArc}
            targetDirection={targetDir.toArray() as [number, number, number]}
          />
        </group>
      </scene>

      {/* Orbit controls for viewer camera */}
      <OrbitControls
        ref={controlsRef}
        enablePan={true}
        enableZoom={true}
        enableRotate={true}
        minDistance={3}
        maxDistance={50}
        target={viewerCamera.target.toArray() as [number, number, number]}
        onChange={(e) => {
          if (onViewerCameraChange && controlsRef.current) {
            onViewerCameraChange(
              threeCamera.position.clone(),
              controlsRef.current.target.clone()
            );
          }
        }}
      />
    </>
  );
}

interface WorldSceneWrapperProps {
  worldState: WorldViewState | null;
  viewerCamera: ViewerCameraState;
  setViewerCamera: (state: ViewerCameraState) => void;
  showTrajectory?: boolean;
  trajectoryPoints?: Vector3[];
  showErrorArc?: boolean;
  showAxes?: boolean;
}

export function WorldSceneWrapper({
  worldState,
  viewerCamera,
  setViewerCamera,
  showTrajectory = true,
  trajectoryPoints = [],
  showErrorArc = true,
  showAxes = true,
}: WorldSceneWrapperProps) {
  const handleViewerCameraChange = (position: Vector3, target: Vector3) => {
    setViewerCamera({
      position,
      target,
      mode: "fixed",
    });
  };

  return (
    <div className="w-full h-full" style={{ width: "100%", height: "100%" }}>
      <Canvas
        camera={{ fov: 50, near: 0.1, far: 100 }}
        style={{ width: "100%", height: "100%", display: "block" }}
        onCreated={({ gl }) => {
          gl.setClearColor(WORLD_VIEW_COLORS.background, 1);
        }}
      >
        <WorldScene
          worldState={worldState}
          viewerCamera={viewerCamera}
          setViewerCamera={setViewerCamera}
          showTrajectory={showTrajectory}
          trajectoryPoints={trajectoryPoints}
          showErrorArc={showErrorArc}
          showAxes={showAxes}
          onViewerCameraChange={handleViewerCameraChange}
        />
      </Canvas>
    </div>
  );
}