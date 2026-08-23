"""Tesseract backend (priority 4: lightest Python dependency, needs the
Tesseract binary installed separately -- flat text only).

Port reference: the ``backend == "tesseract"`` branches in
`meeting_pipeline/ocr_engine.py`. Import `pytesseract` (and `PIL.Image`)
lazily; `pytesseract.get_tesseract_version()` doubles as the availability
check during backend selection (raises if the binary isn't installed).
"""

from __future__ import annotations

from pathlib import Path

from .....core.models import SpatialOCRResult


class TesseractBackend:
    """TODO:
      - `__init__`: lazy `import pytesseract`, call
        `pytesseract.get_tesseract_version()` to verify the binary is
        installed (let the caller catch failure to try the next backend).
      - `extract_spatial(image_path)`: `pytesseract.image_to_string(
        Image.open(image_path), config="--psm 6")`, return as flat content.
    """

    def __init__(self) -> None:
        self._available = False

    def extract_spatial(self, image_path: Path) -> SpatialOCRResult:
        raise NotImplementedError
