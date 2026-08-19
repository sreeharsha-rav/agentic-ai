"""Pure image-comparison and content-scoring functions.

Hand-rolled SSIM/MSE (no ``scikit-image`` dependency) plus a composite
"is this frame slide/code/document content, or just a webcam view" score
built entirely from classical OpenCV signals (edge density, near-white pixel
ratio, horizontal-gradient text-line density). These are pure functions on
numpy arrays with no video I/O, kept separate from ``hybrid_extractor.py`` so
they can be exercised with synthetic arrays in tests.
"""

from __future__ import annotations

import cv2
import numpy as np


def compute_mse(img1: np.ndarray, img2: np.ndarray) -> float:
    """Mean squared pixel difference between two frames, resized to 320x180 grayscale."""
    g1 = cv2.cvtColor(cv2.resize(img1, (320, 180)), cv2.COLOR_BGR2GRAY).astype(np.float32)
    g2 = cv2.cvtColor(cv2.resize(img2, (320, 180)), cv2.COLOR_BGR2GRAY).astype(np.float32)
    return float(np.mean((g1 - g2) ** 2))


def compute_ssim(img1: np.ndarray, img2: np.ndarray) -> float:
    """Structural similarity between two frames, resized to 640x360 grayscale.

    Accepts either grayscale (2-D) or BGR (3-D) input.
    """
    if img1.ndim == 3:
        img1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    if img2.ndim == 3:
        img2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    img1 = cv2.resize(img1, (640, 360)).astype(np.float32)
    img2 = cv2.resize(img2, (640, 360)).astype(np.float32)

    k1, k2, l = 0.01, 0.03, 255
    c1, c2 = (k1 * l) ** 2, (k2 * l) ** 2
    window_size, sigma = 11, 1.5

    mu1 = cv2.GaussianBlur(img1, (window_size, window_size), sigma)
    mu2 = cv2.GaussianBlur(img2, (window_size, window_size), sigma)
    mu1_sq, mu2_sq, mu1_mu2 = mu1**2, mu2**2, mu1 * mu2
    sigma1_sq = cv2.GaussianBlur(img1**2, (window_size, window_size), sigma) - mu1_sq
    sigma2_sq = cv2.GaussianBlur(img2**2, (window_size, window_size), sigma) - mu2_sq
    sigma12 = cv2.GaussianBlur(img1 * img2, (window_size, window_size), sigma) - mu1_mu2

    ssim_map = ((2 * mu1_mu2 + c1) * (2 * sigma12 + c2)) / (
        (mu1_sq + mu2_sq + c1) * (sigma1_sq + sigma2_sq + c2)
    )
    return float(ssim_map.mean())


def laplacian_variance(image: np.ndarray) -> float:
    """Sharpness proxy: variance of the Laplacian. Higher = sharper/more detailed."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def content_score(frame: np.ndarray) -> float:
    """Composite score distinguishing content screens (slides/docs/code) from webcam views.

    Three signals, all computable in pure OpenCV, no model:
      1. Edge density       -- slides/text have high Laplacian variance.
      2. Uniform region      -- slides have a large near-white background area.
      3. Text-line density   -- horizontal Sobel captures text row edges.

    Returns a float in roughly [0, 1]; frames scoring below
    ``FrameExtractionConfig.content_score_threshold`` are classified as
    webcam-only.
    """
    gray = cv2.cvtColor(cv2.resize(frame, (320, 180)), cv2.COLOR_BGR2GRAY)

    lap_var = laplacian_variance(gray)

    _, bright_mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    uniform_ratio = float(np.count_nonzero(bright_mask)) / gray.size

    sobel_h = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    text_line_density = float(np.abs(sobel_h).mean())

    return (
        0.5 * min(lap_var / 1000.0, 1.0)
        + 0.3 * uniform_ratio
        + 0.2 * min(text_line_density / 10.0, 1.0)
    )
