"""EasyOCR backend (priority 3: heaviest, ~1.5s/frame, but the most portable
fallback -- flat text only, no bounding-polygon spatial hierarchy).

Port reference: the ``backend == "easy"`` branches in
`meeting_pipeline/ocr_engine.py`. Import `easyocr` lazily. Unlike
Rapid/Paddle, this backend cannot produce titles/content/details -- everything
goes into `SpatialOCRResult.content` as one flat string.
"""

from __future__ import annotations

from pathlib import Path

from .....core.models import SpatialOCRResult


class EasyOCRBackend:
    """TODO:
      - `__init__`: lazy `import easyocr`, construct
        `easyocr.Reader(["en"], gpu=False, verbose=False)`.
      - `extract_spatial(image_path)`: call
        `self._reader.readtext(str(image_path), detail=0)`, join into flat
        text, return `SpatialOCRResult(content=[flat_text], flat_text=flat_text)`.
    """

    def __init__(self) -> None:
        self._reader = None

    def extract_spatial(self, image_path: Path) -> SpatialOCRResult:
        raise NotImplementedError
