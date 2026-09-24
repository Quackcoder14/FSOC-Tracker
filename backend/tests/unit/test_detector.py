import numpy as np
import cv2
import pytest
from app.detection.candidate_detector import CandidateDetector


def test_detector_finds_beacon():
    detector = CandidateDetector(min_size_px=3, max_size_px=30, target_size_px=10)
    
    # Create black canvas 480x640 with a synthetic Gaussian beacon at (320, 240)
    image = np.zeros((480, 640), dtype=np.uint8)
    cv2.circle(image, (320, 240), 6, 250, -1)
    image = cv2.GaussianBlur(image, (5, 5), 1.5)

    det_result = detector.detect(image)
    assert det_result.detected
    assert det_result.x == pytest.approx(320.0, abs=2.0)
    assert det_result.y == pytest.approx(240.0, abs=2.0)
    assert det_result.confidence > 0.5


def test_detector_no_beacon_on_blank():
    detector = CandidateDetector()
    blank = np.zeros((480, 640), dtype=np.uint8)
    det_result = detector.detect(blank)
    assert not det_result.detected
    assert det_result.x is None
    assert det_result.candidate_count == 0
