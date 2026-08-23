"""Unit tests for `media/image_metrics.py`.

Port reference: `../../../meeting_pipeline/tests/test_image_metrics.py` --
exercises `compute_ssim`/`compute_mse`/`content_score` against small
synthetic numpy arrays (solid colors, checkerboards, injected noise), no
real image files required. Same approach applies directly here since the
functions are ported unchanged.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="media/image_metrics.py not yet implemented")
def test_ssim_of_identical_frames_is_one():
    ...


@pytest.mark.skip(reason="media/image_metrics.py not yet implemented")
def test_ssim_of_very_different_frames_is_low():
    ...


@pytest.mark.skip(reason="media/image_metrics.py not yet implemented")
def test_content_score_high_for_text_like_pattern():
    ...


@pytest.mark.skip(reason="media/image_metrics.py not yet implemented")
def test_content_score_low_for_uniform_frame():
    ...
