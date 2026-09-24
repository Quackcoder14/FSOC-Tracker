"""
AI Validator — lightweight CNN beacon classifier via ONNX Runtime.

Architecture:
  Classical candidates → crop → CNN inference → beacon probability → rescore

Falls back gracefully to classical CV when model is unavailable.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from app.core.models import Candidate

logger = logging.getLogger(__name__)

# ONNX Runtime import with fallback
try:
    import onnxruntime as ort
    _ORT_AVAILABLE = True
except ImportError:
    _ORT_AVAILABLE = False
    logger.warning("ONNX Runtime not available — AI validation disabled")


# ---------------------------------------------------------------------------
# Model input specification
# ---------------------------------------------------------------------------

MODEL_INPUT_SIZE = 32   # 32×32 grayscale crop
MODEL_INPUT_NAME = "input"
MODEL_OUTPUT_NAME = "output"


class AIValidator:
    """
    Wraps an ONNX Runtime inference session for beacon classification.

    If model is unavailable or disabled, returns None ai_score for all candidates
    and leaves final_score = cv_score unchanged.
    """

    def __init__(
        self,
        model_path: str | Path,
        enabled: bool = True,
        confidence_threshold: float = 0.7,
        invoke_on_ambiguous: bool = True,
        max_candidates_for_ai: int = 5,
    ) -> None:
        self._path      = Path(model_path)
        self._enabled   = enabled
        self._threshold = confidence_threshold
        self._invoke_on_ambiguous = invoke_on_ambiguous
        self._max_candidates = max_candidates_for_ai
        self._session: Optional["ort.InferenceSession"] = None
        self._model_version = "unknown"
        self._available = False

        if enabled:
            self._load()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    @property
    def available(self) -> bool:
        return self._available

    @property
    def model_version(self) -> str:
        return self._model_version

    def validate_candidates(
        self,
        image: np.ndarray,
        candidates: list[Candidate],
        force: bool = False,
    ) -> list[Candidate]:
        """
        Run AI validation on candidates that need it.

        AI is invoked when:
          - force=True
          - multiple candidates present (disambiguation)
          - best CV score is ambiguous (below high-confidence threshold)

        Returns updated candidate list with ai_score and final_score set.
        """
        if not candidates:
            return candidates

        if not self._available:
            return candidates  # Passthrough — classical scores unchanged

        # Determine whether to invoke AI
        should_run = (
            force
            or len(candidates) > 1
            or (self._invoke_on_ambiguous and candidates[0].final_score < 0.85)
        )

        if not should_run:
            return candidates

        # Convert image to grayscale for cropping
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        updated = []
        for c in candidates[:self._max_candidates]:
            ai_score = self._infer_single(gray, c)
            if ai_score is not None:
                # Blend AI score (60%) with CV score (40%)
                final = 0.6 * ai_score + 0.4 * c.cv_score
            else:
                final = c.cv_score

            updated.append(Candidate(
                x=c.x, y=c.y, area=c.area, brightness=c.brightness,
                shape_score=c.shape_score, proximity_score=c.proximity_score,
                cv_score=c.cv_score,
                ai_score=ai_score,
                final_score=final,
            ))

        # Append remaining candidates without AI (unchanged)
        updated.extend(candidates[self._max_candidates:])
        return updated

    # ------------------------------------------------------------------ #
    # Inference
    # ------------------------------------------------------------------ #

    def _infer_single(self, gray: np.ndarray, c: Candidate) -> Optional[float]:
        """Crop candidate region and run inference. Returns beacon probability."""
        h, w = gray.shape[:2]
        half = MODEL_INPUT_SIZE // 2
        cx, cy = int(round(c.x)), int(round(c.y))

        # Crop centered on candidate, padded
        x1 = max(cx - half, 0)
        y1 = max(cy - half, 0)
        x2 = min(cx + half, w)
        y2 = min(cy + half, h)

        crop = gray[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        # Resize to model input size
        crop_resized = cv2.resize(crop, (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE),
                                  interpolation=cv2.INTER_LINEAR).astype(np.float32)

        # Robust contrast normalization: subtract local background floor so haze/sky offset doesn't suppress beacon
        c_min = float(crop_resized.min())
        c_max = float(crop_resized.max())
        dynamic_range = c_max - c_min
        if dynamic_range > 10.0:
            inp_norm = (crop_resized - c_min) / dynamic_range
        else:
            inp_norm = crop_resized / 255.0

        inp = inp_norm[np.newaxis, np.newaxis, :, :]  # (1, 1, H, W)

        try:
            input_name = self._session.get_inputs()[0].name
            outputs = self._session.run(None, {input_name: inp})
            out = np.asarray(outputs[0]).flatten()
            if len(out) == 1:
                # Binary classification with Sigmoid output
                prob = float(out[0])
            elif len(out) >= 2:
                # 2-class logits/softmax: [non-beacon, beacon]
                exp = np.exp(out - out.max())
                probs = exp / exp.sum()
                prob = float(probs[1])
            else:
                return None
            return float(np.clip(prob, 0.0, 1.0))
        except Exception as e:
            logger.debug("AI inference error: %s", e)
            return None

    # ------------------------------------------------------------------ #
    # Model management
    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        if not _ORT_AVAILABLE:
            logger.warning("ONNX Runtime not installed. AI validation disabled.")
            return

        if not self._path.exists():
            logger.warning("AI model not found at %s — using classical CV fallback", self._path)
            return

        try:
            opts = ort.SessionOptions()
            opts.inter_op_num_threads = 1
            opts.intra_op_num_threads = 2
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            self._session = ort.InferenceSession(
                str(self._path),
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )

            # Warmup pass
            dummy = np.zeros((1, 1, MODEL_INPUT_SIZE, MODEL_INPUT_SIZE), dtype=np.float32)
            self._session.run(None, {MODEL_INPUT_NAME: dummy})

            self._available = True
            self._model_version = self._path.stem
            logger.info("AI validator loaded: %s", self._path)

        except Exception as e:
            logger.error("Failed to load AI model: %s — falling back to classical CV", e)
            self._session = None

    def get_status(self) -> dict:
        return {
            "available": self._available,
            "model_path": str(self._path),
            "model_version": self._model_version,
            "enabled": self._enabled,
        }
