"""
Message definitions and serializers for Python <-> Frontend communication.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional
import json

try:
    import msgpack
    _MSGPACK_AVAILABLE = True
except ImportError:
    _MSGPACK_AVAILABLE = False


class CommandType(str, Enum):
    START_SIMULATION = "START_SIMULATION"
    START_BENCHMARK = "START_BENCHMARK"
    STOP = "STOP"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    STEP = "STEP"
    SET_MODE = "SET_MODE"
    UPDATE_DISTURBANCES = "UPDATE_DISTURBANCES"
    UPDATE_TRAJECTORY = "UPDATE_TRAJECTORY"
    UPDATE_CAMERA = "UPDATE_CAMERA"
    SET_SCENARIO = "SET_SCENARIO"
    GENERATE_REPORT = "GENERATE_REPORT"
    PING = "PING"
    UPLOAD_VIDEO = "UPLOAD_VIDEO"
    UPLOAD_GT = "UPLOAD_GT"


class MessageType(str, Enum):
    FRAME_UPDATE = "FRAME_UPDATE"
    STATUS = "STATUS"
    REPORT_READY = "REPORT_READY"
    PONG = "PONG"
    ERROR = "ERROR"
    COMMAND_APPLIED = "COMMAND_APPLIED"
    COMMAND_ERROR = "COMMAND_ERROR"


def serialize_message(data: dict, use_msgpack: bool = False) -> bytes:
    """Serializes a dictionary payload to bytes (MessagePack or JSON UTF-8)."""
    if use_msgpack and _MSGPACK_AVAILABLE:
        return msgpack.packb(data, use_bin_type=True)
    return json.dumps(data).encode("utf-8")


def deserialize_message(raw_bytes: bytes) -> dict:
    """Deserializes raw bytes into a dictionary, trying MessagePack then JSON."""
    if _MSGPACK_AVAILABLE:
        try:
            return msgpack.unpackb(raw_bytes, raw=False)
        except Exception:
            pass

    # Fallback to UTF-8 JSON
    text = raw_bytes.decode("utf-8")
    return json.loads(text)
