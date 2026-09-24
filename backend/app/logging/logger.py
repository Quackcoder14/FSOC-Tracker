"""
Structured logging setup for FSOC tracking system.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path


# Event type constants (logged as structured fields)
class Events:
    SYSTEM_START = "SYSTEM_START"
    SOURCE_STARTED = "SOURCE_STARTED"
    TARGET_ACQUIRED = "TARGET_ACQUIRED"
    TRACKING_STARTED = "TRACKING_STARTED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    TARGET_LOST = "TARGET_LOST"
    REACQUISITION_STARTED = "REACQUISITION_STARTED"
    TARGET_REACQUIRED = "TARGET_REACQUIRED"
    BENCHMARK_STARTED = "BENCHMARK_STARTED"
    BENCHMARK_COMPLETED = "BENCHMARK_COMPLETED"
    REPORT_GENERATED = "REPORT_GENERATED"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"


def setup_logging(
    level: str = "INFO",
    log_to_file: bool = True,
    log_dir: str = "logs",
    run_id: str | None = None,
) -> logging.Logger:
    """
    Configure root logger with console + optional file handlers.
    Returns the root logger.
    """
    level_int = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level_int)
    root.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level_int)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # File handler
    if log_to_file:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        ts = run_id or datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        fh = logging.FileHandler(log_path / f"fsoc_{ts}.log", encoding="utf-8")
        fh.setLevel(level_int)
        fh.setFormatter(fmt)
        root.addHandler(fh)

    return root


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
