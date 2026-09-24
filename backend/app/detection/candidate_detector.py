"""
Classical beacon candidate detector for FSOC tracking.

Pipeline:
  gray + binary → connected components → candidate filtering → scored candidates

The detector does NOT know about ground truth.
It uses only the image and (optionally) the Kalman predicted position.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import cv2
import numpy as np

from app.core.models import Candidate, DetectionResult
from app.detection.centroid import calculate_centroid
from app.detection.preprocess import Preprocessor

logger = logging.getLogger(__name__)


class CandidateDetector:
    """
    Detects beacon candidates using classical computer vision.

    Scoring rubric (each 0–1, summed with weights):
      - brightness:   normalized mean pixel intensity
      - shape:        compactness (circularity)
      - size:         inverse distance from configured beacon size
      - proximity:    distance from Kalman predicted position (if available)
    """

    def __init__(
        self,
        min_area_px: float = 3.0,
        max_area_px: float = 2000.0,
        min_brightness: float = 30.0,
        min_size_px: int = 3,
        max_size_px: int = 40,
        target_size_px: int = 10,
        max_aspect_ratio: float = 4.0,
        proximity_weight: float = 0.25,
        proximity_radius_px: float = 120.0,
        preprocessor: Optional[Preprocessor] = None,
    ) -> None:
        self.min_area         = min_area_px
        self.max_area         = max_area_px
        self.min_brightness   = min_brightness
        self.min_size_px      = min_size_px
        self.max_size_px      = max_size_px
        self.target_size_px   = target_size_px
        self.max_aspect_ratio = max_aspect_ratio
        self.proximity_weight = proximity_weight
        self.proximity_radius = proximity_radius_px

        self._preprocessor = preprocessor or Preprocessor()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def detect(
        self,
        image: np.ndarray,
        predicted_x: Optional[float] = None,
        predicted_y: Optional[float] = None,
    ) -> DetectionResult:
        """
        Run detection on a single frame.
        predicted_x/y: Kalman prediction for proximity scoring (or None).
        """
        gray, binary, norm = self._preprocessor.process(image)
        candidates = self._extract_candidates(gray, binary, norm, predicted_x, predicted_y)

        if not candidates:
            return DetectionResult(
                detected=False, x=None, y=None,
                confidence=0.0, candidate_count=0, candidates=[])

        # Sort by final score, highest first
        candidates.sort(key=lambda c: c.final_score, reverse=True)
        best = candidates[0]

        return DetectionResult(
            detected=True,
            x=best.x,
            y=best.y,
            confidence=best.final_score,
            candidate_count=len(candidates),
            candidates=candidates,
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _extract_candidates(
        self,
        gray: np.ndarray,
        binary: np.ndarray,
        norm: np.ndarray,
        pred_x: Optional[float],
        pred_y: Optional[float],
    ) -> list[Candidate]:

        # Connected components analysis
        n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            binary, connectivity=8, ltype=cv2.CV_32S
        )

        candidates = []

        for i in range(1, n_labels):  # Skip background (label 0)
            x  = int(stats[i, cv2.CC_STAT_LEFT])
            y  = int(stats[i, cv2.CC_STAT_TOP])
            w  = int(stats[i, cv2.CC_STAT_WIDTH])
            h  = int(stats[i, cv2.CC_STAT_HEIGHT])
            area = float(stats[i, cv2.CC_STAT_AREA])

            # Area filter
            if area < self.min_area or area > self.max_area:
                continue

            # Size filter
            max_dim = max(w, h)
            if max_dim < self.min_size_px or max_dim > self.max_size_px:
                continue

            # Aspect ratio filter
            if h > 0 and w / h > self.max_aspect_ratio:
                continue
            if w > 0 and h / w > self.max_aspect_ratio:
                continue

            # Extract the candidate ROI
            mask_roi = (labels[y:y+h, x:x+w] == i).astype(np.uint8) * 255
            gray_roi = gray[y:y+h, x:x+w]

            # Brightness filter
            mean_br = float(gray_roi[mask_roi > 0].mean()) if mask_roi.any() else 0
            if mean_br < self.min_brightness:
                continue

            # Compute centroid
            cx, cy = calculate_centroid(gray, binary, (x, y, w, h))

            # Scoring
            brightness_score = float(np.clip(mean_br / 200.0, 0, 1))
            shape_score      = self._compactness(area, w, h)
            size_score       = self._size_score(max_dim)
            prox_score       = self._proximity_score(cx, cy, pred_x, pred_y)

            # Intrinsic visual score
            w_bright = 0.40
            w_shape  = 0.35
            w_size   = 0.25
            intrinsic_score = (
                w_bright * brightness_score +
                w_shape  * shape_score +
                w_size   * size_score
            ) / (w_bright + w_shape + w_size)

            # Composite CV score
            if pred_x is not None and pred_y is not None:
                w_prox = self.proximity_weight
                cv_score = (intrinsic_score * (1.0 - w_prox)) + (prox_score * w_prox)
                # Safeguard: if visually pristine, ensure high score
                if intrinsic_score > 0.75:
                    cv_score = max(cv_score, intrinsic_score * 0.85)
            else:
                cv_score = intrinsic_score

            candidates.append(Candidate(
                x=cx, y=cy,
                area=area,
                brightness=mean_br,
                shape_score=shape_score,
                proximity_score=prox_score,
                cv_score=cv_score,
                ai_score=None,
                final_score=cv_score,
            ))

        return candidates

    @staticmethod
    def _compactness(area: float, w: int, h: int) -> float:
        """
        Circularity measure: 4π·A / P² → 1 for circle, <1 for irregular.
        Approximated using bounding box diagonal as perimeter proxy.
        """
        if w <= 0 or h <= 0:
            return 0.0
        # Perimeter approximation for ellipse-like shapes
        p = math.pi * (3 * (w + h) / 2 - math.sqrt((3 * w + h) * (w + 3 * h))) / 2
        p = max(p, 1e-9)
        compactness = 4 * math.pi * area / (p * p)
        return float(np.clip(compactness, 0, 1))

    def _size_score(self, dim_px: float) -> float:
        """Score based on proximity to target_size_px."""
        diff = abs(dim_px - self.target_size_px)
        tolerance = max(self.max_size_px - self.min_size_px, 1)
        return float(np.clip(1.0 - diff / tolerance, 0, 1))

    def _proximity_score(
        self,
        cx: float, cy: float,
        pred_x: Optional[float], pred_y: Optional[float],
    ) -> float:
        if pred_x is None or pred_y is None:
            return 0.5  # Neutral when no prediction available
        dist = math.hypot(cx - pred_x, cy - pred_y)
        sigma = self.proximity_radius / 2.0
        score = math.exp(-0.5 * (dist / sigma) ** 2)
        return float(np.clip(score, 0.15, 1.0))
