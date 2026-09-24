"""
Ground truth reader and exporter for benchmark and evaluation modes.

Supports CSV and JSON formats with automatic header detection and validation.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class GroundTruthPoint:
    frame_index: int
    timestamp_ms: float
    target_x: float
    target_y: float
    target_pan_deg: Optional[float] = None
    target_tilt_deg: Optional[float] = None


class GroundTruthLoader:
    """
    Loads, indexes, and queries ground truth trajectory data.
    """

    def __init__(self) -> None:
        self._points: Dict[int, GroundTruthPoint] = {}
        self._ordered: List[GroundTruthPoint] = []

    def clear(self) -> None:
        self._points.clear()
        self._ordered.clear()

    @property
    def total_frames(self) -> int:
        return len(self._ordered)

    def load(self, file_path: Union[str, Path]) -> int:
        """
        Loads ground truth from CSV or JSON.
        Returns number of points loaded.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Ground truth file not found: {path}")

        self.clear()
        if path.suffix.lower() == ".csv":
            self._load_csv(path)
        elif path.suffix.lower() == ".json":
            self._load_json(path)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}. Expected .csv or .json")

        logger.info("Loaded %d ground truth points from %s", len(self._points), path.name)
        return len(self._points)

    def _load_csv(self, path: Path) -> None:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # Normalize field names to lowercase
            fieldnames = [c.strip().lower() for c in (reader.fieldnames or [])]
            
            # Identify columns
            frame_col = next((c for c in fieldnames if c in ("frame_index", "frame", "frame_idx", "idx")), None)
            time_col = next((c for c in fieldnames if c in ("timestamp_ms", "time_ms", "timestamp", "t")), None)
            x_col = next((c for c in fieldnames if c in ("target_x", "x", "px", "target_px_x", "gt_x")), None)
            y_col = next((c for c in fieldnames if c in ("target_y", "y", "py", "target_px_y", "gt_y")), None)
            pan_col = next((c for c in fieldnames if c in ("target_pan_deg", "pan_deg", "pan")), None)
            tilt_col = next((c for c in fieldnames if c in ("target_tilt_deg", "tilt_deg", "tilt")), None)

            if not x_col or not y_col:
                raise ValueError(f"CSV {path} must contain target_x and target_y columns. Found: {reader.fieldnames}")

            idx = 0
            for row in reader:
                norm_row = {k.strip().lower(): v for k, v in row.items()}
                try:
                    f_idx = int(float(norm_row[frame_col])) if frame_col and norm_row.get(frame_col) else idx
                    t_ms = float(norm_row[time_col]) if time_col and norm_row.get(time_col) else f_idx * 33.333
                    tx = float(norm_row[x_col])
                    ty = float(norm_row[y_col])
                    tpan = float(norm_row[pan_col]) if pan_col and norm_row.get(pan_col) else None
                    ttilt = float(norm_row[tilt_col]) if tilt_col and norm_row.get(tilt_col) else None

                    pt = GroundTruthPoint(
                        frame_index=f_idx,
                        timestamp_ms=t_ms,
                        target_x=tx,
                        target_y=ty,
                        target_pan_deg=tpan,
                        target_tilt_deg=ttilt,
                    )
                    self._points[f_idx] = pt
                    self._ordered.append(pt)
                    idx += 1
                except (ValueError, TypeError) as e:
                    logger.warning("Skipping invalid ground truth row %d: %s", idx, e)
                    continue

    def _load_json(self, path: Path) -> None:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        points_list = data if isinstance(data, list) else data.get("frames", data.get("ground_truth", []))
        for idx, item in enumerate(points_list):
            f_idx = int(item.get("frame_index", item.get("frame", idx)))
            t_ms = float(item.get("timestamp_ms", item.get("time_ms", f_idx * 33.333)))
            tx = float(item.get("target_x", item.get("x", 0.0)))
            ty = float(item.get("target_y", item.get("y", 0.0)))
            tpan = float(item["target_pan_deg"]) if "target_pan_deg" in item else None
            ttilt = float(item["target_tilt_deg"]) if "target_tilt_deg" in item else None

            pt = GroundTruthPoint(
                frame_index=f_idx,
                timestamp_ms=t_ms,
                target_x=tx,
                target_y=ty,
                target_pan_deg=tpan,
                target_tilt_deg=ttilt,
            )
            self._points[f_idx] = pt
            self._ordered.append(pt)

    def get_for_frame(self, frame_index: int) -> Optional[GroundTruthPoint]:
        """Lookup ground truth point by frame index."""
        if frame_index in self._points:
            return self._points[frame_index]
        if 0 <= frame_index < len(self._ordered):
            return self._ordered[frame_index]
        return None

    @staticmethod
    def export_csv(points: List[GroundTruthPoint], output_path: Union[str, Path]) -> None:
        """Exports points to CSV format."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["frame_index", "timestamp_ms", "target_x", "target_y", "target_pan_deg", "target_tilt_deg"])
            for pt in points:
                writer.writerow([
                    pt.frame_index,
                    f"{pt.timestamp_ms:.2f}",
                    f"{pt.target_x:.3f}",
                    f"{pt.target_y:.3f}",
                    f"{pt.target_pan_deg:.4f}" if pt.target_pan_deg is not None else "",
                    f"{pt.target_tilt_deg:.4f}" if pt.target_tilt_deg is not None else "",
                ])
