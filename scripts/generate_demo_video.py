"""
Generates synthetic benchmark test videos and matching ground truth CSV files.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
import cv2
import numpy as np

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.simulation.camera import VirtualCamera
from app.simulation.target import CircularTrajectory, Figure8Trajectory


def generate_benchmark_clip(
    output_video: Path,
    output_csv: Path,
    traj_type: str = "circular",
    duration_s: float = 6.0,
    fps: float = 30.0,
    width: int = 640,
    height: int = 480,
):
    output_video.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    camera = VirtualCamera(width=width, height=height, hfov_deg=4.0, vfov_deg=3.0)
    camera.reset()

    if traj_type == "figure8":
        traj = Figure8Trajectory(speed_deg_s=1.2, amplitude_x_deg=1.2, amplitude_y_deg=0.8)
    else:
        traj = CircularTrajectory(speed_deg_s=1.2, amplitude_x_deg=1.0, amplitude_y_deg=0.7)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_video), fourcc, fps, (width, height), isColor=True)

    total_frames = int(duration_s * fps)
    gt_rows = []

    for f_idx in range(total_frames):
        t = f_idx / fps
        t_ms = t * 1000.0
        ts = traj.get_state(t)

        px, py = camera.world_to_pixel(ts.pan_deg, ts.tilt_deg)

        # Render frame
        img = np.zeros((height, width, 3), dtype=np.uint8)
        # Background starry noise
        noise = np.random.normal(10, 5, (height, width, 3)).astype(np.uint8)
        img = cv2.add(img, noise)

        # Draw beacon
        if 0 <= px < width and 0 <= py < height:
            cv2.circle(img, (int(px), int(py)), int(ts.size_px / 2), (240, 240, 255), -1)
            img = cv2.GaussianBlur(img, (7, 7), 2.0)

        writer.write(img)

        gt_rows.append([f_idx, f"{t_ms:.2f}", f"{px:.3f}", f"{py:.3f}", f"{ts.pan_deg:.4f}", f"{ts.tilt_deg:.4f}"])

    writer.release()

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        csv_w = csv.writer(f)
        csv_w.writerow(["frame_index", "timestamp_ms", "target_x", "target_y", "target_pan_deg", "target_tilt_deg"])
        csv_w.writerows(gt_rows)

    print(f"Generated {total_frames} frames -> {output_video} & {output_csv}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
    generate_benchmark_clip(
        Path("data/demo/clean/clean_trajectory.mp4"),
        Path("data/demo/clean/ground_truth.csv"),
    )
