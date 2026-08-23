"""`OCREngine`: tries each backend in priority order, first successful
import+initialization wins; falls back to a "none" (transcript-only) mode if
every backend is unavailable.

Port reference: `OCREngine._init_engine()`/`extract_spatial()`/`extract()`
in `meeting_pipeline/ocr_engine.py`. This is the ONE place in the codebase
that knows the backend priority order and constructs a concrete backend --
`stages/context/service.py` and `stages/align/ingestion/image_ingester.py`
both depend on this class (via `core.interfaces.OCRBackend`), never on an
individual backend module.
"""

from __future__ import annotations

from pathlib import Path

from ....config.schema import OCRConfig
from ....core.interfaces import OCRBackend
from ....core.models import SpatialOCRResult
from .spatial_layout import SpatialLayoutExtractor

_BACKEND_PRIORITY = ("rapid", "paddle", "easy", "tesseract", "none")


class OCREngine(OCRBackend):
    """TODO: port `_init_engine()`'s try/except-per-backend loop from
    `ocr_engine.py::OCREngine`, importing each backend class from
    `backends/` lazily and falling through to the next on any exception.
    `extract_spatial()` delegates to whichever backend was selected, or
    returns an empty `SpatialOCRResult` if `self.backend == "none"`.
    """

    def __init__(self, config: OCRConfig) -> None:
        self.config = config
        self.backend: str | None = None
        self._spatial_extractor = SpatialLayoutExtractor(config)
        self._impl = None  # the selected backend instance, once resolved

    def extract_spatial(self, image_path: Path) -> SpatialOCRResult:
        raise NotImplementedError
