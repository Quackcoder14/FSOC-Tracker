"""
Generate demo benchmark dataset (MP4 video + ground-truth CSV) for FSOC Tracker.
Uses VirtualCamera projection to ensure ground truth matches visual beacon location.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
import cv2
import numpy as np

# Ensure backend can be imported
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.simulation.camera import VirtualCamera
from app.simulation.target import CircularTrajectory


def generate_demo_dataset(
    output_dir: Path | str = "data/demo/clean",
    num_frames: int = 300,
    fps: float = 30.0,
    width: int = 640,
    height: int = 480,
    hfov_deg: float = 4.0,
    vfov_deg: float = 3.0,
) -> tuple[Path, Path]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    video_path = out_dir / "clean_trajectory.mp4"
    csv_path = out_dir / "ground_truth.csv"

    camera = VirtualCamera(
        width=width,
        height=height,
        hfov_deg=hfov_deg,
        vfov_deg=vfov_deg,
    )
    camera.reset()

    traj = CircularTrajectory(
        speed_deg_s=1.2,
        amplitude_x_deg=1.2,
        amplitude_y_deg=0.8,
        size_px=10,
        brightness=230,
    )

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height), isColor=True)

    gt_rows: list[list[str | int | float]] = []

    for f_idx in range(num_frames):
        t = f_idx / fps
        t_ms = t * 1000.0
        ts = traj.get_state(t)

        px, py = camera.world_to_pixel(ts.pan_deg, ts.tilt_deg)

        # Render frame using camera scene renderer
        targets = [{
            "pan_deg": ts.pan_deg,
            "tilt_deg": ts.tilt_deg,
            "size_px": ts.size_px,
            "brightness": ts.brightness,
        }]
        frame_bgr = camera.render_scene(targets, background_brightness=15)
        writer.write(frame_bgr)

        gt_rows.append([
            f_idx,
            f"{t_ms:.2f}",
            f"{px:.3f}",
            f"{py:.3f}",
            f"{ts.pan_deg:.4f}",
            f"{ts.tilt_deg:.4f}",
        ])

    writer.release()

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        csv_w = csv.writer(f)
        csv_w.writerow([
            "frame_index",
            "timestamp_ms",
            "target_x",
            "target_y",
            "target_pan_deg",
            "target_tilt_deg",
        ])
        csv_w.writerows(gt_rows)

    print(f"Demo dataset generated:\n  Video: {video_path}\n  CSV:   {csv_path} ({num_frames} frames)")
    return video_path, csv_path


if __name__ == "__main__":
    generate_demo_dataset()
