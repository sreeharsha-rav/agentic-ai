"""PaddleOCR backend (priority 2: alternative, works well on macOS, also
returns bounding polygons -> full spatial hierarchy).

Port reference: the ``backend == "paddle"`` branches in
`meeting_pipeline/ocr_engine.py`. Import `paddleocr` lazily.
"""

from __future__ import annotations

from pathlib import Path

from .....core.models import SpatialOCRResult
from ..spatial_layout import SpatialLayoutExtractor


class PaddleOCRBackend:
    """TODO:
      - `__init__`: lazy `from paddleocr import PaddleOCR`, construct with
        `use_angle_cls=False, lang="en", show_log=False, use_gpu=False`.
      - `extract_spatial(image_path)`: call `self._reader.ocr(str(image_path),
        cls=False)`, reshape into the `(polygon, text, score)` triples
        `SpatialLayoutExtractor.decompose()` expects.
    """

    def __init__(self, spatial_extractor: SpatialLayoutExtractor) -> None:
        self._spatial_extractor = spatial_extractor
        self._reader = None

    def extract_spatial(self, image_path: Path) -> SpatialOCRResult:
        raise NotImplementedError
