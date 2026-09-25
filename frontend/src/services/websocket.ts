import { TelemetryPacket, DisturbanceConfig, CommandResult, CameraConfig } from "../types/telemetry";

type Listener<T> = (data: T) => void;

export type BenchmarkState = "ready" | "running" | "paused" | "completed" | "failed";

export interface BenchmarkStatus {
  state: BenchmarkState;
  framesProcessed?: number;
  framesEvaluated?: number;
  currentRmse?: number;
  currentLockRetention?: number;
  currentFps?: number;
  currentLatency?: number;
}

export class WebSocketService {
  private ws: WebSocket | null = null;
  private url: string;
  private baseReconnectInterval: number = 500;
  private maxReconnectInterval: number = 8000;
  private reconnectInterval: number = 500;
  private shouldReconnect: boolean = true;
  private connectionState: "disconnected" | "connecting" | "connected" = "disconnected";
  private connectionGeneration: number = 0;
  private connectionAttemptInProgress: boolean = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  private telemetryListeners: Set<Listener<TelemetryPacket>> = new Set();
  private statusListeners: Set<Listener<any>> = new Set();
  private reportListeners: Set<Listener<any>> = new Set();
  private commandResultListeners: Set<Listener<CommandResult>> = new Set();
  private connectionListeners: Set<Listener<boolean>> = new Set();
  private benchmarkStatusListeners: Set<Listener<BenchmarkStatus>> = new Set();

  public isConnected: boolean = false;

  constructor(url?: string) {
    // Use environment variable if available, otherwise use provided URL or default
    this.url = url || (import.meta.env.VITE_BACKEND_WS_URL as string) || "ws://127.0.0.1:8765";
  }

  public connect(): void {
    // Prevent multiple simultaneous connection attempts
    if (this.connectionState === "connected" || this.connectionState === "connecting") {
      return;
    }
    if (this.connectionAttemptInProgress) {
      return;
    }

    this.shouldReconnect = true;
    this.connectionState = "connecting";
    this.connectionAttemptInProgress = true;
    this.connectionGeneration++;

    const currentGeneration = this.connectionGeneration;

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        // Only proceed if this is still the current connection generation
        if (currentGeneration !== this.connectionGeneration) {
          this.ws?.close();
          return;
        }
        this.connectionAttemptInProgress = false;
        this.reconnectInterval = this.baseReconnectInterval; // Reset backoff on successful connection
        this.isConnected = true;
        this.connectionState = "connected";
        console.log("[WebSocket] Connected to", this.url);
        this.notifyConnection(true);
      };

      this.ws.onclose = (event) => {
        // Only handle if this is still the current connection generation
        if (currentGeneration !== this.connectionGeneration) {
          return;
        }
        this.connectionAttemptInProgress = false;
        this.isConnected = false;
        this.connectionState = "disconnected";
        console.log("[WebSocket] Disconnected:", event.code, event.reason || "no reason");
        this.notifyConnection(false);

        if (this.shouldReconnect) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = (event) => {
        // Only handle if this is still the current connection generation
        if (currentGeneration !== this.connectionGeneration) {
          return;
        }
        this.connectionAttemptInProgress = false;
        this.isConnected = false;
        this.connectionState = "disconnected";
        console.warn("[WebSocket] Error:", event);
        this.notifyConnection(false);
        // onclose will be called after onerror, which will trigger reconnect
      };

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "FRAME_UPDATE") {
            this.telemetryListeners.forEach((fn) => fn(data as TelemetryPacket));
            
            // Extract benchmark / run status from telemetry
            if (data.tracking) {
              const status: BenchmarkStatus = {
                state: "running",
                framesProcessed: (data.frame_index ?? 0) + 1,
                framesEvaluated: (data.frame_index ?? 0) + 1,
                currentRmse: data.performance?.rmse_px ?? data.performance?.instant_error_px,
                currentLockRetention: data.performance?.lock_retention_pct,
                currentFps: data.performance?.fps,
                currentLatency: data.performance?.latency_ms,
              };
              this.notifyBenchmarkStatus(status);
            }
          } else if (data.type === "STATUS") {
            if (data.completed) {
              this.notifyBenchmarkStatus({ state: "completed" });
            }
            this.statusListeners.forEach((fn) => fn(data));
          } else if (data.type === "REPORT_READY") {
            this.reportListeners.forEach((fn) => fn(data));
          } else if (data.type === "COMMAND_APPLIED" || data.type === "COMMAND_ERROR") {
            this.commandResultListeners.forEach((fn) => fn(data as CommandResult));
          }
        } catch (e) {
          console.error("Error parsing WebSocket packet", e);
        }
      };
    } catch (e) {
      this.connectionAttemptInProgress = false;
      this.isConnected = false;
      this.connectionState = "disconnected";
      console.error("[WebSocket] Connection failed:", e);
      this.notifyConnection(false);
      if (this.shouldReconnect) {
        this.scheduleReconnect();
      }
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }
    if (!this.shouldReconnect) {
      return;
    }
    console.log(`[WebSocket] Scheduling reconnect in ${this.reconnectInterval}ms`);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      // Exponential backoff with cap
      this.reconnectInterval = Math.min(this.reconnectInterval * 2, this.maxReconnectInterval);
      this.connect();
    }, this.reconnectInterval);
  }

  public disconnect(): void {
    this.shouldReconnect = false;
    this.connectionGeneration++; // Invalidate any pending operations
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.isConnected = false;
    this.connectionState = "disconnected";
    this.connectionAttemptInProgress = false;
  }

  public getConnectionState(): "disconnected" | "connecting" | "connected" {
    return this.connectionState;
  }

  public send(payload: any): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
    } else {
      console.warn("[WebSocket] Cannot send, socket not open:", this.ws?.readyState);
    }
  }

  public startSimulation(): void {
    this.send({ command: "START_SIMULATION" });
  }

  public startBenchmark(): void {
    this.send({ command: "START_BENCHMARK" });
  }

  public stop(): void {
    this.send({ command: "STOP" });
  }

  public pause(): void {
    this.send({ command: "PAUSE" });
  }

  public resume(): void {
    this.send({ command: "RESUME" });
  }

  public step(): void {
    this.send({ command: "STEP" });
  }

  public setMode(mode: string, video_path?: string, gt_path?: string): void {
    this.send({ command: "SET_MODE", mode, video_path, gt_path });
  }

  public updateDisturbances(disturbances: Partial<DisturbanceConfig>): void {
    this.send({ command: "UPDATE_DISTURBANCES", disturbances });
  }

  public updateTrajectory(trajectory: Record<string, any>): void {
    this.send({ command: "UPDATE_TRAJECTORY", trajectory });
  }

  public setScenario(scenario: string, params?: Record<string, any>): void {
    this.send({ command: "SET_SCENARIO", scenario, params: params || {} });
  }

  public generateReport(): void {
    this.send({ command: "GENERATE_REPORT" });
  }

  public updateCamera(camera: Partial<CameraConfig>): void {
    this.send({ command: "UPDATE_CAMERA", camera });
  }

  public uploadVideo(filename: string, data: string): void {
    this.send({ command: "UPLOAD_VIDEO", filename, data });
  }

  public uploadGt(filename: string, data: string): void {
    this.send({ command: "UPLOAD_GT", filename, data });
  }

  public onCommandResult(fn: Listener<CommandResult>): () => void {
    this.commandResultListeners.add(fn);
    return () => this.commandResultListeners.delete(fn);
  }

  public onTelemetry(fn: Listener<TelemetryPacket>): () => void {
    this.telemetryListeners.add(fn);
    return () => this.telemetryListeners.delete(fn);
  }

  public onStatus(fn: Listener<any>): () => void {
    this.statusListeners.add(fn);
    return () => this.statusListeners.delete(fn);
  }

  public onReport(fn: Listener<any>): () => void {
    this.reportListeners.add(fn);
    return () => this.reportListeners.delete(fn);
  }

  public onConnectionChange(fn: Listener<boolean>): () => void {
    this.connectionListeners.add(fn);
    fn(this.isConnected);
    return () => this.connectionListeners.delete(fn);
  }

  public onBenchmarkStatus(fn: Listener<BenchmarkStatus>): () => void {
    this.benchmarkStatusListeners.add(fn);
    return () => this.benchmarkStatusListeners.delete(fn);
  }

  private notifyConnection(state: boolean): void {
    this.connectionListeners.forEach((fn) => fn(state));
  }

  private notifyBenchmarkStatus(status: BenchmarkStatus): void {
    this.benchmarkStatusListeners.forEach((fn) => fn(status));
  }
}

export const wsService = new WebSocketService();