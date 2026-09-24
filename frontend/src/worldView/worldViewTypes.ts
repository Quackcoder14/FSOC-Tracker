import { Vector3, Euler } from "three";

export interface WorldTelemetry {
  target_position: [number, number, number];
  camera_position: [number, number, number];
  camera_pan_deg: number;
  camera_tilt_deg: number;
  boresight_direction: [number, number, number];
  hfov_deg: number;
  vfov_deg: number;
  target_distance: number;
}

export interface WorldViewState {
  targetPosition: Vector3;
  cameraPosition: Vector3;
  cameraRotation: Euler; // x = tilt, y = pan
  boresightDirection: Vector3;
  hfovDeg: number;
  vfovDeg: number;
  targetDistance: number;
}

export interface ViewerCameraState {
  position: Vector3;
  target: Vector3;
  mode: "fixed" | "follow_camera" | "follow_target";
}

export type ViewMode = "camera_pov" | "world_view" | "split";

export const DEFAULT_VIEWER_CAMERA_STATE: ViewerCameraState = {
  position: new Vector3(0, 8, 15),
  target: new Vector3(0, 0, 5),
  mode: "fixed",
};

export const WORLD_VIEW_COLORS = {
  background: 0x070B12,
  grid: 0x1A2839,
  cameraBody: 0x4A5A6A,
  cameraFrustum: 0x1F78B4,
  target: 0xF28C28,
  boresight: 0xE8EDF3,
  trajectory: 0x26364A,
  axes: {
    x: 0xD9534F,
    y: 0x38A169,
    z: 0x1F78B4,
  },
  errorArc: 0xF28C28,
};

export const WORLD_VIEW_CONSTANTS = {
  targetDistance: 10,
  cameraSize: 0.5,
  frustumLength: 10,
  trajectoryMaxPoints: 200,
  gridSize: 20,
  gridDivisions: 20,
};