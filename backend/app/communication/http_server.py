"""
HTTP Upload Server for FSOC Tracker.

Runs alongside the WebSocket server on a separate port (default 8766).
Provides a simple file upload endpoint so the browser can send video and
ground-truth files to the backend before starting a benchmark run.

Endpoints
---------
POST /upload/video   — Accepts a multipart/form-data upload with field "file".
                       Saves to <upload_dir>/video_<timestamp>.<ext>
                       Returns: {"path": "/abs/path", "filename": "...", "ok": true}

POST /upload/gt      — Same for ground-truth CSV/JSON files.
                       Saves to <upload_dir>/gt_<timestamp>.<ext>

GET  /health         — Returns {"ok": true} for connectivity checks.

CORS
----
All responses include permissive CORS headers so the browser (running on
localhost:5173 in dev, or the same origin in production) can reach port 8766.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

from aiohttp import web

logger = logging.getLogger(__name__)

# Where uploaded files are stored (created on first upload)
_DEFAULT_UPLOAD_DIR = Path("results") / "uploads"


def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


def _json_ok(data: dict) -> web.Response:
    return web.json_response({**data, "ok": True}, headers=_cors_headers())


def _json_err(message: str, status: int = 400) -> web.Response:
    return web.json_response({"ok": False, "error": message}, status=status, headers=_cors_headers())


async def _handle_options(request: web.Request) -> web.Response:
    """Pre-flight CORS handler."""
    return web.Response(status=204, headers=_cors_headers())


async def _handle_health(request: web.Request) -> web.Response:
    return _json_ok({"status": "ready"})


async def _handle_upload(request: web.Request, prefix: str, allowed_exts: set[str]) -> web.Response:
    """
    Generic multipart file upload handler.

    Parameters
    ----------
    prefix      : short label used in the saved filename ("video" or "gt")
    allowed_exts: set of lowercase extensions without dot (e.g. {"mp4","avi"})
    """
    upload_dir: Path = request.app["upload_dir"]
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Parse multipart body
    try:
        reader = await request.multipart()
    except Exception as exc:
        logger.warning("Failed to parse multipart body: %s", exc)
        return _json_err("Expected multipart/form-data body")

    # Iterate fields looking for "file"
    field = None
    async for part in reader:
        if part.name == "file":
            field = part
            break

    if field is None:
        return _json_err("No field named 'file' in multipart body")

    # Validate extension
    original_name = field.filename or f"{prefix}_upload"
    ext = Path(original_name).suffix.lstrip(".").lower()
    if ext not in allowed_exts:
        return _json_err(
            f"Unsupported file type '.{ext}'. Allowed: {sorted(allowed_exts)}"
        )

    # Build destination path with timestamp to avoid collisions
    ts = int(time.time() * 1000)
    dest_name = f"{prefix}_{ts}.{ext}"
    dest_path = upload_dir / dest_name

    # Stream file to disk
    try:
        written = 0
        with dest_path.open("wb") as fout:
            while True:
                chunk = await field.read_chunk(65536)  # 64 KB chunks
                if not chunk:
                    break
                fout.write(chunk)
                written += len(chunk)
    except Exception as exc:
        logger.error("Failed writing upload to %s: %s", dest_path, exc)
        # Clean up partial file
        dest_path.unlink(missing_ok=True)
        return _json_err(f"Write failed: {exc}", status=500)

    logger.info(
        "Upload received: %s → %s (%.1f KB)",
        original_name,
        dest_path,
        written / 1024,
    )

    return _json_ok({
        "path": str(dest_path.resolve()),
        "filename": dest_name,
        "original_name": original_name,
        "size_bytes": written,
    })


async def _handle_video_upload(request: web.Request) -> web.Response:
    return await _handle_upload(
        request,
        prefix="video",
        allowed_exts={"mp4", "mkv", "avi", "mov", "wmv"},
    )


async def _handle_gt_upload(request: web.Request) -> web.Response:
    return await _handle_upload(
        request,
        prefix="gt",
        allowed_exts={"csv", "json"},
    )


def create_app(upload_dir: Optional[Path] = None) -> web.Application:
    """Build and return the aiohttp Application."""
    app = web.Application(
        # Allow up to 2 GB for large video files
        client_max_size=2 * 1024 ** 3,
    )
    app["upload_dir"] = Path(upload_dir or _DEFAULT_UPLOAD_DIR)

    # Routes
    app.router.add_route("OPTIONS", "/{path_info:.*}", _handle_options)
    app.router.add_get("/health", _handle_health)
    app.router.add_post("/upload/video", _handle_video_upload)
    app.router.add_post("/upload/gt", _handle_gt_upload)

    return app


class HttpUploadServer:
    """
    Thin wrapper around the aiohttp app for consistent lifecycle management.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8766,
                 upload_dir: Optional[Path] = None) -> None:
        self.host = host
        self.port = port
        self._app = create_app(upload_dir)
        self._runner: Optional[web.AppRunner] = None

    async def start(self) -> None:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        logger.info("HTTP upload server listening on http://%s:%d", self.host, self.port)

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            logger.info("HTTP upload server stopped")
