#!/usr/bin/env python3
"""
Generate synthetic benchmark data for FSOC tracker.

Creates:
1. MP4 video with moving beacon
2. Ground truth CSV with frame-indexed positions
"""

from __future__ import annotations

import argparse
import csv
import math
import os
from pathlib import Path

import cv2
import numpy as np


def generate_benchmark_dataset(
    output_dir: str = "data/benchmark",
    video_name: str = "synthetic_benchmark.mp4",
    gt_name: str = "synthetic_ground_truth.csv",
    width: int = 640,
    height: int = 480,
    fps: float = 30.0,
    duration_s: float = 30.0,
    trajectory_type: str = "figure8",
    beacon_size: int = 10,
    beacon_brightness: int = 220,
    seed: int = 42,
) -> tuple[str, str]:
    """
    Generate synthetic benchmark video and ground truth.
    
    Returns:
        (video_path, gt_path)
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    video_path = output_path / video_name
    gt_path = output_path / gt_name
    
    total_frames = int(duration_s * fps)
    
    rng = np.random.default_rng(seed)
    
    # Generate trajectory
    if trajectory_type == "figure8":
        trajectory = generate_figure8_trajectory(
            total_frames, fps, width, height, seed=seed
        )
    elif trajectory_type == "circular":
        trajectory = generate_circular_trajectory(
            total_frames, fps, width, height, seed=seed
        )
    elif trajectory_type == "linear":
        trajectory = generate_linear_trajectory(
            total_frames, fps, width, height, seed=seed
        )
    else:
        raise ValueError(f"Unknown trajectory type: {trajectory_type}")
    
    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(
        str(video_path), fourcc, fps, (width, height), isColor=True
    )
    
    # Ground truth data
    gt_data = []
    
    # Star field (static for realism)
    star_count = 100
    star_xs = rng.integers(0, width, size=star_count)
    star_ys = rng.integers(0, height, size=star_count)
    star_br = rng.integers(40, 120, size=star_count)
    
    for frame_idx in range(len(trajectory)):
        pan_deg, tilt_deg, size_px, brightness = trajectory[frame_idx]
        
        # Create frame
        frame = np.full((height, width, 3), 20, dtype=np.uint8)
        
        # Draw stars
        for sx, sy, sb in zip(star_xs, star_ys, star_br):
            frame[sy, sx] = [sb, sb, sb]
        
        # Convert world to pixel (using a virtual camera at origin)
        # This simulates the camera at (0,0) looking at the target
        # The target's world position is (pan_deg, tilt_deg) in angular space
        # Project to pixel: cx + pan_deg * px_per_deg, cy - tilt_deg * px_per_deg
        hfov = 4.0
        vfov = 3.0
        px_per_deg_x = width / hfov
        px_per_deg_y = height / vfov
        cx = width / 2
        cy = height / 2
        
        # Convert to pixel coordinates
        target_px = cx + pan_deg * px_per_deg_x
        target_py = cy - tilt_deg * px_per_deg_y
        
        # Only draw if in frame (with margin for beacon size)
        margin = int(size_px * 3)
        if -margin <= target_px < width + margin and -margin <= target_py < height + margin:
            # Draw Gaussian-profile beacon
            size_px = max(1, int(size_px))
            sigma = size_px / 2.0
            target_x = int(round(target_px))
            target_y = int(round(target_py))
            
            for dy in range(-size_px * 3, size_px * 3 + 1):
                for dx in range(-size_px * 3, size_px * 3 + 1):
                    ix, iy = target_x + dx, target_y + dy
                    if 0 <= ix < width and 0 <= iy < height:
                        dist_sq = dx * dx + dy * dy
                        val = brightness * math.exp(-dist_sq / (2 * sigma * sigma))
                        val = int(np.clip(val, 0, 255))
                        frame[iy, ix] = np.clip(
                            frame[iy, ix].astype(np.int32) + np.array([val, val, int(val * 0.9)]),
                            0, 255
                        ).astype(np.uint8)
        
        # Write frame
        writer.write(frame)
        
        # Record ground truth
        gt_data.append({
            "frame_index": frame_idx,
            "target_x": target_px,
            "target_y": target_py,
            "target_pan_deg": pan_deg,
            "target_tilt_deg": tilt_deg,
        })
    
    writer.release()
    
    # Write ground truth CSV
    with open(gt_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["frame_index", "target_x", "target_y", "target_pan_deg", "target_tilt_deg"])
        for row in gt_data:
            writer.writerow([
                row["frame_index"],
                f"{row['target_x']:.4f}",
                f"{row['target_y']:.4f}",
                f"{row['target_pan_deg']:.6f}",
                f"{row['target_tilt_deg']:.6f}",
            ])
    
    print(f"Generated {len(gt_data)} frames")
    print(f"Video: {video_path}")
    print(f"Ground truth: {gt_path}")
    
    return str(video_path), str(gt_path)


def generate_figure8_trajectory(
    total_frames: int,
    fps: float,
    width: int,
    height: int,
    amplitude_x: float = 1.5,
    amplitude_y: float = 1.0,
    speed_deg_s: float = 2.0,
    seed: int = 42,
) -> list:
    """Generate figure-8 trajectory in angular space."""
    import math
    trajectory = []
    period = 2 * math.pi * max(amplitude_x, amplitude_y) / speed_deg_s
    w = 2 * math.pi / period
    
    for frame_idx in range(total_frames):
        t = frame_idx / fps
        pan = amplitude_x * math.sin(w * t)
        tilt = amplitude_y * math.sin(2 * w * t)
        size_px = 10
        brightness = 220
        trajectory.append((pan, tilt, size_px, 220))
    
    return trajectory


def generate_circular_trajectory(
    total_frames: int,
    fps: float,
    width: int,
    height: int,
    amplitude_x: float = 1.0,
    amplitude_y: float = 0.7,
    speed_deg_s: float = 1.5,
    seed: int = 42,
) -> list:
    """Generate circular trajectory in angular space."""
    import math
    trajectory = []
    period = 2 * math.pi * max(amplitude_x, amplitude_y) / speed_deg_s
    w = 2 * math.pi / period
    
    for frame_idx in range(total_frames):
        t = frame_idx / fps
        pan = amplitude_x * math.cos(w * t)
        tilt = amplitude_y * math.sin(w * t)
        size_px = 10
        brightness = 220
        trajectory.append((pan, tilt, size_px, 220))
    
    return trajectory


def generate_linear_trajectory(
    total_frames: int,
    fps: float,
    width: int,
    height: int,
    start_pan: float = -1.5,
    start_tilt: float = 0.0,
    vel_pan: float = 0.5,
    vel_tilt: float = 0.1,
    seed: int = 42,
) -> list:
    """Generate linear trajectory in angular space."""
    trajectory = []
    
    for frame_idx in range(total_frames):
        t = frame_idx / fps
        pan = start_pan + vel_pan * t
        tilt = start_tilt + vel_tilt * t
        size_px = 10
        brightness = 220
        trajectory.append((pan, tilt, size_px, 220))
    
    return trajectory


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic FSOC benchmark data")
    parser.add_argument("--output-dir", default="data/benchmark", help="Output directory")
    parser.add_argument("--video-name", default="synthetic_benchmark.mp4", help="Video filename")
    parser.add_argument("--gt-name", default="synthetic_ground_truth.csv", help="Ground truth filename")
    parser.add_argument("--width", type=int, default=640, help="Video width")
    parser.add_argument("--height", type=int, default=480, help="Video height")
    parser.add_argument("--fps", type=float, default=30.0, help="Frames per second")
    parser.add_argument("--duration", type=float, default=30.0, help="Duration in seconds")
    parser.add_argument("--trajectory", default="figure8", choices=["figure8", "circular", "linear"], help="Trajectory type")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    
    args = parser.parse_args()
    
    video_path, gt_path = generate_benchmark_dataset(
        output_dir=args.output_dir,
        video_name=args.video_name,
        gt_name=args.gt_name,
        width=args.width,
        height=args.height,
        fps=args.fps,
        duration_s=args.duration,
        trajectory_type=args.trajectory,
        seed=args.seed,
    )
    
    print(f"\nSuccess!")
    print(f"Video: {video_path}")
    print(f"Ground truth: {gt_path}")