from __future__ import annotations

import numpy as np
import pytest

from meeting_pipeline.image_metrics import compute_mse, compute_ssim, content_score, laplacian_variance


def _solid_bgr(value: int, shape=(360, 640, 3)) -> np.ndarray:
    return np.full(shape, value, dtype=np.uint8)


def test_compute_mse_identical_is_zero():
    img = _solid_bgr(128)
    assert compute_mse(img, img) == 0.0


def test_compute_mse_black_vs_white():
    black = _solid_bgr(0)
    white = _solid_bgr(255)
    assert compute_mse(black, white) == pytest.approx(65025.0, rel=1e-3)


def test_compute_ssim_identical_is_one():
    img = _solid_bgr(128)
    assert compute_ssim(img, img) == pytest.approx(1.0, abs=1e-3)


def test_compute_ssim_black_vs_white_is_low():
    black = _solid_bgr(0)
    white = _solid_bgr(255)
    assert compute_ssim(black, white) < 0.1


def test_compute_ssim_accepts_grayscale_and_bgr_consistently():
    rng = np.random.default_rng(0)
    bgr1 = rng.integers(0, 255, size=(360, 640, 3), dtype=np.uint8)
    bgr2 = rng.integers(0, 255, size=(360, 640, 3), dtype=np.uint8)
    import cv2

    gray1 = cv2.cvtColor(bgr1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(bgr2, cv2.COLOR_BGR2GRAY)
    assert compute_ssim(bgr1, bgr2) == pytest.approx(compute_ssim(gray1, gray2), abs=1e-6)


def test_compute_ssim_tolerates_mismatched_sizes():
    a = _solid_bgr(100, shape=(200, 300, 3))
    b = _solid_bgr(100, shape=(400, 800, 3))
    assert compute_ssim(a, b) == pytest.approx(1.0, abs=1e-3)


def test_compute_metrics_are_deterministic():
    rng = np.random.default_rng(1)
    a = rng.integers(0, 255, size=(360, 640, 3), dtype=np.uint8)
    b = rng.integers(0, 255, size=(360, 640, 3), dtype=np.uint8)
    assert compute_ssim(a, b) == compute_ssim(a, b)
    assert compute_mse(a, b) == compute_mse(a, b)


def test_laplacian_variance_flat_image_is_near_zero():
    assert laplacian_variance(_solid_bgr(100)) == pytest.approx(0.0, abs=1e-6)


def test_content_score_slide_beats_webcam_noise():
    # Synthetic "slide": a bright background with black horizontal bars
    # standing in for lines of text -- should score highly on all 3 signals.
    slide = np.full((720, 1280, 3), 245, dtype=np.uint8)
    for y in range(40, 700, 20):
        slide[y : y + 4, 80:1200] = 10

    # Synthetic "webcam": smoothed mid-gray random noise, no text-like edges
    # or bright uniform background.
    rng = np.random.default_rng(42)
    noise = rng.integers(80, 160, size=(720, 1280, 3), dtype=np.uint8)
    import cv2

    webcam = cv2.GaussianBlur(noise, (25, 25), 8)

    slide_score = content_score(slide)
    webcam_score = content_score(webcam)

    assert slide_score > webcam_score
    assert slide_score >= 0.15  # clears the default FrameExtractionConfig threshold
    assert webcam_score < 0.15  # stays below it
