"""
Synthetic Dataset Generator for Beacon AI Validator.

Generates 32x32 grayscale crops for:
  - Positive class (label 1): genuine optical beacons with varying Gaussian blur,
    intensities, sizes, and atmospheric degradation.
  - Negative class (label 0): clutter, ambient noise, glints, edges, and background artifacts.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import random
import cv2
import numpy as np


def generate_positive_crop(size: int = 32) -> np.ndarray:
    """Generate a single 32x32 positive beacon crop."""
    crop = np.zeros((size, size), dtype=np.float32)

    # Beacon centroid near center (with small jitter +/- 4 px)
    cx = size / 2.0 + random.uniform(-4.0, 4.0)
    cy = size / 2.0 + random.uniform(-4.0, 4.0)
    radius = random.uniform(2.5, 7.0)
    peak_intensity = random.uniform(160.0, 255.0)

    # 2D Gaussian profile
    y, x = np.ogrid[:size, :size]
    dist_sq = (x - cx) ** 2 + (y - cy) ** 2
    beacon = peak_intensity * np.exp(-dist_sq / (2.0 * (radius / 2.0) ** 2))
    crop += beacon

    # Ambient low background noise
    bg_level = random.uniform(5.0, 40.0)
    noise = np.random.normal(bg_level, random.uniform(3.0, 15.0), (size, size))
    crop += noise

    # Occasional blur or haze
    if random.random() < 0.3:
        ksize = random.choice([3, 5])
        crop = cv2.GaussianBlur(crop, (ksize, ksize), 0)

    crop = np.clip(crop, 0.0, 255.0).astype(np.uint8)
    return crop


def generate_negative_crop(size: int = 32) -> np.ndarray:
    """Generate a single 32x32 negative non-beacon crop."""
    neg_type = random.choice(["uniform_noise", "edge", "bright_streak", "salt_pepper", "diffuse_blob"])
    crop = np.zeros((size, size), dtype=np.float32)

    if neg_type == "uniform_noise":
        bg = random.uniform(10.0, 80.0)
        crop = np.random.normal(bg, random.uniform(5.0, 25.0), (size, size))

    elif neg_type == "edge":
        # Simulates horizon or building/strut edge
        bg = random.uniform(20.0, 60.0)
        crop += bg
        angle = random.uniform(0, np.pi)
        for i in range(size):
            for j in range(size):
                if (i * np.cos(angle) + j * np.sin(angle)) > size / 2.0:
                    crop[i, j] += random.uniform(40.0, 100.0)

    elif neg_type == "bright_streak":
        # Non-circular reflection or cosmic ray / sensor streak
        x1, y1 = random.randint(0, size - 1), random.randint(0, size - 1)
        x2, y2 = random.randint(0, size - 1), random.randint(0, size - 1)
        temp = np.zeros((size, size), dtype=np.uint8)
        cv2.line(temp, (x1, y1), (x2, y2), int(random.uniform(150, 255)), thickness=random.randint(1, 2))
        crop += temp.astype(np.float32)

    elif neg_type == "salt_pepper":
        crop = np.random.uniform(0, 30, (size, size))
        num_sp = random.randint(5, 20)
        for _ in range(num_sp):
            rx, ry = random.randint(0, size - 1), random.randint(0, size - 1)
            crop[ry, rx] = random.uniform(180, 255)

    elif neg_type == "diffuse_blob":
        # Very wide, non-compact diffuse light (e.g. distant streetlamp or cloud)
        cx, cy = size / 2.0, size / 2.0
        y, x = np.ogrid[:size, :size]
        dist_sq = (x - cx) ** 2 + (y - cy) ** 2
        crop += 120.0 * np.exp(-dist_sq / (2.0 * 18.0 ** 2))

    crop = np.clip(crop, 0.0, 255.0).astype(np.uint8)
    return crop


def build_dataset(output_dir: Path, num_train: int = 2000, num_val: int = 500):
    for split, count in [("train", num_train), ("val", num_val)]:
        pos_dir = output_dir / split / "1_beacon"
        neg_dir = output_dir / split / "0_clutter"
        pos_dir.mkdir(parents=True, exist_ok=True)
        neg_dir.mkdir(parents=True, exist_ok=True)

        n_pos = count // 2
        n_neg = count - n_pos

        for i in range(n_pos):
            img = generate_positive_crop(32)
            cv2.imwrite(str(pos_dir / f"beacon_{i:05d}.png"), img)

        for i in range(n_neg):
            img = generate_negative_crop(32)
            cv2.imwrite(str(neg_dir / f"clutter_{i:05d}.png"), img)

    print(f"Dataset generated at {output_dir}: {num_train} train, {num_val} val images.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=str, default="data/dataset")
    parser.add_argument("--train-samples", type=int, default=1500)
    parser.add_argument("--val-samples", type=int, default=400)
    args = parser.parse_args()

    build_dataset(Path(args.output_dir), args.train_samples, args.val_samples)
