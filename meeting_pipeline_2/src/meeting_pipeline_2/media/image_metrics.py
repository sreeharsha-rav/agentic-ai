"""Pure image-comparison and content-scoring functions.

Port reference: `meeting_pipeline/image_metrics.py` in full -- these are
already pure functions on numpy arrays with no video I/O, which is exactly
the shape this scaffold wants: kept here unchanged so `stages/frames/`'s
dedup/scene-detection logic can unit-test against synthetic arrays, no video
file or OpenCV video decoding required.
"""

from __future__ import annotations

import numpy as np


def compute_mse(img1: np.ndarray, img2: np.ndarray) -> float:
    """Mean squared pixel difference between two frames.

    TODO: port from `image_metrics.py::compute_mse()`.
    """
    raise NotImplementedError


def compute_ssim(img1: np.ndarray, img2: np.ndarray) -> float:
    """Structural similarity between two frames.

    TODO: port from `image_metrics.py::compute_ssim()` (hand-rolled, no
    scikit-image dependency).
    """
    raise NotImplementedError


def laplacian_variance(image: np.ndarray) -> float:
    """Sharpness proxy: variance of the Laplacian.

    TODO: port from `image_metrics.py::laplacian_variance()`.
    """
    raise NotImplementedError


def content_score(frame: np.ndarray) -> float:
    """Composite score distinguishing content screens (slides/docs/code)
    from webcam views.

    TODO: port from `image_metrics.py::content_score()` (edge density +
    near-white ratio + horizontal text-line density, weighted 0.5/0.3/0.2).
    """
    raise NotImplementedError
