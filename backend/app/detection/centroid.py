"""
Intensity-weighted centroid calculator for FSOC beacon candidates.
"""

from __future__ import annotations

from typing import Tuple, Optional
import numpy as np
import cv2


def geometric_centroid(mask: np.ndarray, bbox: Tuple[int, int, int, int]) -> Tuple[float, float]:
    """
    Calculate geometric centroid of pixels inside a bounding box on a binary mask.
    bbox: (x, y, w, h) in OpenCV convention.
    """
    x, y, w, h = bbox
    roi = mask[y:y+h, x:x+w]
    ys, xs = np.nonzero(roi)
    if len(xs) == 0:
        return float(x + w / 2), float(y + h / 2)
    return float(np.mean(xs) + x), float(np.mean(ys) + y)


def intensity_weighted_centroid(
    gray: np.ndarray,
    mask: np.ndarray,
    bbox: Tuple[int, int, int, int],
    min_weight_sum: float = 1.0,
) -> Tuple[float, float]:
    """
    Calculate intensity-weighted centroid (subpixel accuracy).

    Weights pixels by their grayscale intensity, giving more influence
    to the brightest part of the beacon (actual optical emitter position).

    bbox: (x, y, w, h)
    min_weight_sum: safety threshold to avoid division by zero.
    """
    x, y, w, h = bbox
    roi_gray = gray[y:y+h, x:x+w].astype(np.float64)
    roi_mask = mask[y:y+h, x:x+w]

    # Apply mask — only consider candidate pixels
    roi_weights = roi_gray * (roi_mask > 0).astype(np.float64)

    weight_sum = roi_weights.sum()
    if weight_sum < min_weight_sum:
        # Fallback to geometric centroid
        return geometric_centroid(mask, bbox)

    # Build coordinate grids
    ys_grid, xs_grid = np.mgrid[y:y+h, x:x+w]

    cx = float(np.sum(xs_grid * roi_weights) / weight_sum)
    cy = float(np.sum(ys_grid * roi_weights) / weight_sum)
    return cx, cy


def calculate_centroid(
    gray: np.ndarray,
    binary: np.ndarray,
    bbox: Tuple[int, int, int, int],
    use_weighted: bool = True,
) -> Tuple[float, float]:
    """
    Choose between weighted and geometric centroid automatically.
    Uses weighted centroid when candidate is bright enough.
    """
    x, y, w, h = bbox
    roi_gray = gray[y:y+h, x:x+w]
    mean_brightness = float(roi_gray.mean())

    if use_weighted and mean_brightness > 30:
        return intensity_weighted_centroid(gray, binary, bbox)
    else:
        return geometric_centroid(binary, bbox)
