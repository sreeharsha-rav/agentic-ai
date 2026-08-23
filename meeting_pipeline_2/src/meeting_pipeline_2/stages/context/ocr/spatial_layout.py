"""Decomposes raw OCR bounding boxes into a titles/content/details hierarchy
using relative percentile font sizing and 2D spatial zoning.

Port reference: `SpatialLayoutExtractor` in `meeting_pipeline/ocr_engine.py`
in full (percentile-based title/detail height thresholds, top/bottom margin
perimeter rejection, sidebar-zone detail detection). Pure geometry + text
cleaning, no OCR backend dependency -- takes already-extracted
``(polygon, text, score)`` boxes, so it's unit-testable with synthetic box
lists, no image file or OCR engine required.
"""

from __future__ import annotations

from ....config.schema import OCRConfig
from ....core.models import SpatialOCRResult


class SpatialLayoutExtractor:
    """TODO: port `decompose()` from `ocr_engine.py::SpatialLayoutExtractor`,
    including the percentile-based title/detail height thresholds and the
    top/bottom-margin perimeter rejection (OS taskbar / browser chrome)."""

    def __init__(self, config: OCRConfig) -> None:
        self.config = config

    def decompose(self, raw_boxes: list, img_width: int, img_height: int) -> SpatialOCRResult:
        raise NotImplementedError
