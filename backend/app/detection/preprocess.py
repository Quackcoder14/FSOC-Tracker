"""
Preprocessing pipeline for FSOC beacon detection.
Operates on BGR uint8 images; returns grayscale uint8.
"""

from __future__ import annotations

import cv2
import numpy as np


class Preprocessor:
    """
    Configurable preprocessing pipeline.

    Pipeline:
      BGR → grayscale → denoise → normalize → adaptive threshold → morphological cleanup
    """

    def __init__(
        self,
        denoise_strength: int = 3,     # Gaussian kernel size (0 = skip)
        normalize: bool = True,
        threshold_block_size: int = 21, # Adaptive threshold block size (odd number)
        threshold_c: int = -5,          # Subtracted from mean (negative = bright spots)
        morph_kernel_size: int = 3,
    ) -> None:
        self.denoise_strength     = denoise_strength if denoise_strength % 2 == 1 else denoise_strength + 1
        self.normalize            = normalize
        self.threshold_block_size = threshold_block_size if threshold_block_size % 2 == 1 else threshold_block_size + 1
        self.threshold_c          = threshold_c
        self.morph_kernel_size    = morph_kernel_size

        self._morph_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (morph_kernel_size, morph_kernel_size),
        )

    def process(self, image: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Process a BGR or grayscale frame.

        Returns:
          gray   — grayscale image
          binary — thresholded binary image (for connected components)
          norm   — normalized grayscale (for intensity calculations)
        """
        # Step 1: Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Step 2: Noise suppression
        if self.denoise_strength > 1:
            gray_smooth = cv2.GaussianBlur(gray, (self.denoise_strength, self.denoise_strength), 0)
        else:
            gray_smooth = gray

        # Step 3: Normalize (CLAHE for robust contrast in dark scenes)
        if self.normalize:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            norm = clahe.apply(gray_smooth)
        else:
            norm = gray_smooth

        # Step 4: Adaptive thresholding — bright spots on dark background
        # THRESH_BINARY_INV + ADAPTIVE_THRESH_MEAN_C with negative C
        # highlights bright regions.
        binary = cv2.adaptiveThreshold(
            norm,
            255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY,
            self.threshold_block_size,
            self.threshold_c,
        )

        # Also include a global top-percentile threshold for very bright beacons
        _, bright_mask = cv2.threshold(gray_smooth, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        binary = cv2.bitwise_or(binary, bright_mask)

        # Step 5: Morphological cleanup — remove tiny isolated noise pixels
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN,  self._morph_kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, self._morph_kernel)

        return gray, binary, norm
