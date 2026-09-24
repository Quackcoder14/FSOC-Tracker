"""
FSOC Coarse Alignment Tracking Engine — Main Entry Point.

Starts the tracking engine and WebSocket server sidecar.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config.loader import load_config
from app.core.engine import Engine
from app.communication.ws_server import WebSocketServer
from app.communication.http_server import HttpUploadServer

logger = logging.getLogger("fsoc")


def parse_args():
    parser = argparse.ArgumentParser(description="FSOC Terminal Tracking Engine Sidecar")
    parser.add_argument("--mode", type=str, default="simulation", choices=["simulation", "benchmark", "video"])
    parser.add_argument("--config", type=str, default="configs/default.yaml", help="Path to config YAML")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="WebSocket bind host")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket bind port")
    parser.add_argument("--http-port", type=int, default=8766, help="HTTP upload server port")
    parser.add_argument("--headless", action="store_true", help="Run simulation headlessly without waiting for UI")
    parser.add_argument("--duration", type=float, default=10.0, help="Duration for headless run (seconds)")
    parser.add_argument("--video", type=str, default=None, help="Video path for benchmark/video mode")
    parser.add_argument("--ground-truth", type=str, default=None, help="Ground truth path for benchmark mode")
    parser.add_argument("--output-dir", type=str, default="results", help="Directory to store reports and logs")
    return parser.parse_args()


async def run_headless(engine: Engine, duration_s: float, output_dir: str):
    logger.info("Running in headless mode for %.1f seconds...", duration_s)
    engine.start()
    await asyncio.sleep(duration_s)
    engine.stop()
    reports = engine.generate_report(output_dir=output_dir)
    logger.info("Headless run completed. Reports written to: %s", reports)


async def main():
    args = parse_args()

    # Configure root logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = backend_dir / config_path

    logger.info("Loading configuration from %s", config_path)
    cfg = load_config(config_path)

    # Instantiate Engine
    engine = Engine(cfg)
    if args.mode != "simulation" or args.video:
        engine.configure_mode(args.mode, video_path=args.video, gt_path=args.ground_truth)

    # Initialize WebSocket Server
    server = WebSocketServer(engine, host=args.host, port=args.port)
    await server.start()

    # Initialize HTTP Upload Server (decoupled from engine)
    http_server = HttpUploadServer(host=args.host, port=args.http_port)
    await http_server.start()

    if args.headless:
        await run_headless(engine, args.duration, args.output_dir)
        await server.stop()
        await http_server.stop()
        return

    # Keep running until cancelled
    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass  # Windows event loop doesn't always implement add_signal_handler

    logger.info("FSOC Engine ready and awaiting frontend connection.")
    try:
        await stop_event.wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        logger.info("Shutting down engine and server...")
        engine.stop()
        await server.stop()
        await http_server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process terminated by user")
