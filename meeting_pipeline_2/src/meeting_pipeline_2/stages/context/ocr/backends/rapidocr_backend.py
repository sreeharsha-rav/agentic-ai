"""RapidOCR backend (priority 1: fastest, recommended default for
Windows/Linux, returns bounding polygons -> full spatial hierarchy).

Port reference: the ``backend == "rapid"`` branches in
`meeting_pipeline/ocr_engine.py::OCREngine._init_engine()` and
`extract_spatial()`. Import `rapidocr_onnxruntime` lazily inside
`__init__`/`extract_spatial`, never at module top.
"""

from __future__ import annotations

from pathlib import Path

from .....core.models import SpatialOCRResult
from ..spatial_layout import SpatialLayoutExtractor


class RapidOCRBackend:
    """TODO:
      - `__init__`: lazy `from rapidocr_onnxruntime import RapidOCR`,
        construct `RapidOCR()`. Let the caller (`engine.py`) catch
        import/construction failure to try the next backend in the chain.
      - `extract_spatial(image_path)`: call `self._reader(str(image_path))`,
        pass the raw boxes to `SpatialLayoutExtractor.decompose()`.
    """

    def __init__(self, spatial_extractor: SpatialLayoutExtractor) -> None:
        self._spatial_extractor = spatial_extractor
        self._reader = None

    def extract_spatial(self, image_path: Path) -> SpatialOCRResult:
        raise NotImplementedError
