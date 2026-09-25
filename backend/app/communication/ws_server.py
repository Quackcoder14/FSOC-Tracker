"""
WebSocket Server for FSOC Tracker.

Provides a low-latency bi-directional channel between the Python backend engine
and the React / Tauri desktop UI.

Command → Response contract
---------------------------
Every command (except STEP, PING, GENERATE_REPORT) receives either:
  COMMAND_APPLIED — with the resulting configuration snapshot
  COMMAND_ERROR   — with error code and message
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional, Set

import websockets
from websockets.server import WebSocketServerProtocol

from app.core.engine import Engine
from app.communication.messages import CommandType, MessageType, serialize_message, deserialize_message

logger = logging.getLogger(__name__)

# Where uploaded files are stored
_UPLOAD_DIR = Path("results") / "uploads"


class WebSocketServer:
    """
    Manages active client connections and dispatches commands to the Engine.
    """

    def __init__(self, engine: Engine, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.engine = engine
        self.host = host
        self.port = port
        self._clients: Set[WebSocketServerProtocol] = set()
        self._server = None
        self._running = False

        # Connect engine's telemetry emission to our broadcast method
        self.engine.set_telemetry_callback(self.broadcast_telemetry)

        # Ensure upload directory exists
        _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        """Start the WebSocket server listening loop."""
        self._running = True
        self._server = await websockets.serve(
            self._handler,
            self.host,
            self.port,
            max_size=10 * 1024 * 1024,  # 10 MB limit for base64 image frames
            ping_interval=20,
            ping_timeout=20,
        )
        logger.info("WebSocket server listening on ws://%s:%d", self.host, self.port)

    async def stop(self) -> None:
        """Stop server and disconnect all clients."""
        self._running = False
        if self._clients:
            close_tasks = [client.close() for client in self._clients]
            await asyncio.gather(*close_tasks, return_exceptions=True)
            self._clients.clear()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("WebSocket server stopped")

    async def broadcast_telemetry(self, payload: dict) -> None:
        """Broadcasts telemetry packet to all connected clients."""
        if not self._clients:
            return

        message_str = json.dumps(payload)
        dead_clients = set()
        for client in self._clients:
            try:
                await client.send(message_str)
            except websockets.ConnectionClosed:
                dead_clients.add(client)
            except Exception as e:
                logger.debug("Failed sending to client: %s", e)
                dead_clients.add(client)

        if dead_clients:
            self._clients.difference_update(dead_clients)

    async def _handler(self, websocket: WebSocketServerProtocol) -> None:
        """Handles incoming client connection."""
        self._clients.add(websocket)
        logger.info("Client connected: %s (total: %d)", websocket.remote_address, len(self._clients))

        # Send initial status
        try:
            await self._reply_status(websocket)

            async for message in websocket:
                await self._process_command(websocket, message)
        except websockets.ConnectionClosed:
            pass
        except Exception as e:
            logger.error("Error handling client message: %s", e, exc_info=True)
        finally:
            self._clients.discard(websocket)
            logger.info("Client disconnected: %s (remaining: %d)", websocket.remote_address, len(self._clients))

    async def _process_command(self, websocket: WebSocketServerProtocol, raw_msg: Any) -> None:
        """Parse and dispatch command from client."""
        cmd = "UNKNOWN"
        try:
            if isinstance(raw_msg, (bytes, bytearray)):
                data = deserialize_message(raw_msg)
            else:
                data = json.loads(raw_msg)

            cmd = data.get("command", data.get("type", "UNKNOWN"))
            logger.info("Received command: %s", cmd)

            # ── Lifecycle commands ────────────────────────────────────
            if cmd == CommandType.START_SIMULATION.value:
                # Ensure we're in simulation mode before starting
                if self.engine.mode != "simulation":
                    self.engine.configure_mode("simulation")
                self.engine.start()
                await self._reply_status(websocket)
                await self._reply_applied(websocket, cmd, {"running": True, "mode": "simulation"})

            elif cmd == CommandType.START_BENCHMARK.value:
                # Ensure we're in benchmark mode before starting
                if self.engine.mode != "benchmark":
                    await self._reply_error(websocket, cmd, "INVALID_MODE",
                                            "Benchmark mode not configured. Use SET_MODE with mode=benchmark first.")
                else:
                    self.engine.start()
                    await self._reply_status(websocket)
                    await self._reply_applied(websocket, cmd, {"running": True, "mode": "benchmark"})

            elif cmd == CommandType.STOP.value:
                self.engine.stop()
                await self._reply_status(websocket)
                await self._reply_applied(websocket, cmd, {"running": False})

            elif cmd == CommandType.PAUSE.value:
                self.engine.pause()
                await self._reply_status(websocket)
                await self._reply_applied(websocket, cmd, {"paused": True})

            elif cmd == CommandType.RESUME.value:
                self.engine.resume()
                await self._reply_status(websocket)
                await self._reply_applied(websocket, cmd, {"paused": False})

            elif cmd == CommandType.STEP.value:
                telemetry = self.engine.step()
                if telemetry:
                    payload = telemetry.to_dict()
                    await websocket.send(json.dumps(payload))

            # ── Mode configuration ───────────────────────────────────
            elif cmd == CommandType.SET_MODE.value:
                mode   = data.get("mode", "simulation")
                vpath  = data.get("video_path")
                gtpath = data.get("gt_path")
                # configure_mode can raise — we catch and report cleanly
                self.engine.configure_mode(mode, video_path=vpath, gt_path=gtpath)
                await self._reply_status(websocket)
                await self._reply_applied(websocket, cmd, {"mode": mode})

            # ── Simulation parameter updates ─────────────────────────
            elif cmd == CommandType.UPDATE_DISTURBANCES.value:
                dist_settings = data.get("disturbances", {})
                self.engine.update_disturbances(dist_settings)
                # Echo back the active disturbance state from the engine
                cfg_echo = {}
                if hasattr(self.engine.source, "get_disturbance_state"):
                    cfg_echo = self.engine.source.get_disturbance_state().__dict__
                await self._reply_applied(websocket, cmd, cfg_echo)

            elif cmd == CommandType.UPDATE_TRAJECTORY.value:
                traj_settings = data.get("trajectory", {})
                self.engine.update_trajectory(traj_settings)
                await self._reply_applied(websocket, cmd, {"trajectory": traj_settings})

            elif cmd == CommandType.UPDATE_CAMERA.value:
                cam_settings = data.get("camera", {})
                self.engine.update_camera(cam_settings)
                await self._reply_applied(websocket, cmd, {"camera": cam_settings})

            elif cmd == CommandType.SET_SCENARIO.value:
                scenario = data.get("scenario", "circular")
                params   = data.get("params", {})
                self.engine.configure_simulation_scenario(scenario, params)
                await self._reply_status(websocket)
                await self._reply_applied(websocket, cmd, {"scenario": scenario, "params": params})

            # ── Reporting ────────────────────────────────────────────
            elif cmd == CommandType.GENERATE_REPORT.value:
                reports = self.engine.generate_report()
                reply = {
                    "type": MessageType.REPORT_READY.value,
                    "html_path": str(reports.get("html", "")),
                    "json_path": str(reports.get("json", "")),
                }
                await websocket.send(json.dumps(reply))

            elif cmd == CommandType.PING.value:
                await websocket.send(json.dumps({"type": MessageType.PONG.value}))

            # ── File uploads ───────────────────────────────────────────
            elif cmd == CommandType.UPLOAD_VIDEO.value:
                filename = data.get("filename", "video_upload.mp4")
                file_data = data.get("data")  # base64 encoded
                if not file_data:
                    await self._reply_error(websocket, cmd, "MISSING_DATA", "No file data provided")
                    continue

                try:
                    # Decode base64 and save file
                    file_bytes = base64.b64decode(file_data)
                    ts = int(time.time() * 1000)
                    ext = Path(filename).suffix.lstrip(".").lower() or "mp4"
                    dest_name = f"video_{ts}.{ext}"
                    dest_path = _UPLOAD_DIR / dest_name

                    with dest_path.open("wb") as f:
                        f.write(file_bytes)

                    logger.info("Video uploaded via WebSocket: %s (%.1f KB)", dest_name, len(file_bytes) / 1024)
                    await self._reply_applied(websocket, cmd, {"path": str(dest_path.resolve()), "filename": dest_name})
                except Exception as e:
                    logger.error("Failed to save uploaded video: %s", e)
                    await self._reply_error(websocket, cmd, "SAVE_FAILED", str(e))

            elif cmd == CommandType.UPLOAD_GT.value:
                filename = data.get("filename", "gt_upload.csv")
                file_data = data.get("data")  # base64 encoded
                if not file_data:
                    await self._reply_error(websocket, cmd, "MISSING_DATA", "No file data provided")
                    continue

                try:
                    # Decode base64 and save file
                    file_bytes = base64.b64decode(file_data)
                    ts = int(time.time() * 1000)
                    ext = Path(filename).suffix.lstrip(".").lower() or "csv"
                    dest_name = f"gt_{ts}.{ext}"
                    dest_path = _UPLOAD_DIR / dest_name

                    with dest_path.open("wb") as f:
                        f.write(file_bytes)

                    logger.info("Ground truth uploaded via WebSocket: %s (%.1f KB)", dest_name, len(file_bytes) / 1024)
                    await self._reply_applied(websocket, cmd, {"path": str(dest_path.resolve()), "filename": dest_name})
                except Exception as e:
                    logger.error("Failed to save uploaded ground truth: %s", e)
                    await self._reply_error(websocket, cmd, "SAVE_FAILED", str(e))

            else:
                await self._reply_error(websocket, cmd, "UNKNOWN_COMMAND",
                                        f"Unrecognised command: {cmd!r}")

        except (ValueError, FileNotFoundError) as e:
            # Expected validation errors — send structured error, not a raw traceback
            logger.warning("Command %s failed (validation): %s", cmd, e)
            await self._reply_error(websocket, cmd, "INVALID_CONFIGURATION", str(e))

        except Exception as e:
            logger.error("Failed to execute command %s: %s", cmd, e, exc_info=True)
            await self._reply_error(websocket, cmd, "INTERNAL_ERROR", str(e))

    # ------------------------------------------------------------------
    # Reply helpers
    # ------------------------------------------------------------------

    async def _reply_status(self, websocket: WebSocketServerProtocol) -> None:
        status = {
            "type": MessageType.STATUS.value,
            "mode": self.engine.mode,
            "running": self.engine.is_running,
            "paused": self.engine.is_paused,
        }
        await websocket.send(json.dumps(status))

    async def _reply_applied(
        self,
        websocket: WebSocketServerProtocol,
        command: str,
        configuration: dict,
    ) -> None:
        reply = {
            "type": MessageType.COMMAND_APPLIED.value,
            "command": command,
            "configuration": configuration,
        }
        await websocket.send(json.dumps(reply))

    async def _reply_error(
        self,
        websocket: WebSocketServerProtocol,
        command: str,
        code: str,
        message: str,
    ) -> None:
        reply = {
            "type": MessageType.COMMAND_ERROR.value,
            "command": command,
            "code": code,
            "message": message,
        }
        await websocket.send(json.dumps(reply))
