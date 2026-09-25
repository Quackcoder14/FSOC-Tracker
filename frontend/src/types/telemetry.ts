export type TrackingState = "SEARCH" | "ACQUIRE" | "TRACK" | "PREDICT" | "REACQUIRE" | "LOST";

export interface Candidate {
  x: number;
  y: number;
  area: number;
  brightness: number;
  cv_score: number;
  ai_score: number | null;
  final_score: number;
}

export interface DetectionTelemetry {
  detected: boolean;
  x: number | null;
  y: number | null;
  confidence: number;
  candidate_count: number;
  candidates: Candidate[];
}

export interface TrackingTelemetry {
  state: TrackingState;
  predicted_x: number;
  predicted_y: number;
  measured_x: number | null;
  measured_y: number | null;
  velocity_x: number;
  velocity_y: number;
  confidence: number;
}

export interface PIDTelemetry {
  p: number;
  i: number;
  d: number;
  output: number;
  integral: number;
}

export interface ControlTelemetry {
  error_x_px: number;
  error_y_px: number;
  error_x_deg: number;
  error_y_deg: number;
  pan_cmd_deg_s: number;
  tilt_cmd_deg_s: number;
  camera_pan_deg: number;
  camera_tilt_deg: number;
  pid_pan?: PIDTelemetry;
  pid_tilt?: PIDTelemetry;
}

export interface PerformanceTelemetry {
  fps: number;
  latency_ms: number;
  lock_retention_pct: number;
  rmse_px: number | null;
  instant_error_px: number | null;
}

export interface GroundTruthTelemetry {
  target_x: number;
  target_y: number;
  target_pan_deg?: number;
  target_tilt_deg?: number;
}

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

export interface TelemetryPacket {
  type: string;
  frame_index: number;
  timestamp_ms: number;
  image_base64?: string;
  detection: DetectionTelemetry | null;
  tracking: TrackingTelemetry | null;
  control: ControlTelemetry | null;
  performance: PerformanceTelemetry | null;
  ground_truth: GroundTruthTelemetry | null;
  world: WorldTelemetry | null;
}

export interface DisturbanceConfig {
  gaussian: { enabled: boolean; sigma: number };
  salt_pepper: { enabled: boolean; probability: number };
  blur: { enabled: boolean; kernel_size: number };
  atmosphere: { type: "clear" | "haze" | "fog" | "rain"; intensity: number };
  low_light: { enabled: boolean; gamma: number };
  camera_jitter: { enabled: boolean; max_px: number };
  platform_motion: { enabled: boolean; max_px: number };
}

export interface CameraConfig {
  hfov_deg: number;
  vfov_deg?: number;
  beacon_size_px?: number;
}

export interface CommandResult {
  type: "COMMAND_APPLIED" | "COMMAND_ERROR";
  command: string;
  status: "applied" | "error";
  result?: Record<string, any>;
  error?: string;
  configuration?: Record<string, any>;
}

