"""OCR backend abstraction and spatial layout decomposition.

Deliberately has NO third-party imports at module level -- every OCR backend
(rapidocr-onnxruntime, paddleocr, easyocr, pytesseract) and PIL are imported
lazily inside methods, tried in priority order, first successful import wins.
This means ``SpatialLayoutExtractor`` (and by extension its unit tests) works
with nothing beyond the stdlib installed; only actually running OCR needs a
backend package.

Backend priority (first that imports and initializes successfully wins):
  1. rapidocr-onnxruntime  -- fastest (~0.15s/frame), best for Windows/Linux.
  2. paddleocr             -- alternative, works on macOS.
  3. easyocr                -- heavier (~1.5s/frame) but most portable.
  4. pytesseract            -- lightweight, needs the Tesseract binary installed.
  5. none                   -- transcript-only mode, no visual text extracted.

Only the rapid/paddle backends produce the full spatial hierarchy
(titles/content/details); easy/tesseract fall back to flat text only. See
docs/ocr_backends.md.
"""

from __future__ import annotations

import logging
import os

from .config import OCRConfig
from .text_cleaning import clean_ocr_text

logger = logging.getLogger(__name__)

_EMPTY_SPATIAL_RESULT = {"titles": [], "content": [], "details": [], "flat_text": ""}


class SpatialLayoutExtractor:
    """Decomposes raw OCR bounding boxes into a titles/content/details hierarchy.

    Works for any shared-screen format (slides, IDE code, browser docs,
    terminal logs, spreadsheets) using relative percentile font sizing and 2D
    spatial zoning -- no layout model, just geometry.
    """

    def __init__(self, config: OCRConfig | None = None) -> None:
        cfg = config or OCRConfig()
        self.top_cut = cfg.top_margin_cut if cfg.crop_margins else 0.0
        self.bottom_cut = cfg.bottom_margin_cut if cfg.crop_margins else 0.0
        self.title_height_multiplier = cfg.title_height_multiplier
        self.title_height_floor = cfg.title_height_floor
        self.detail_height_multiplier = cfg.detail_height_multiplier
        self.title_band_ratio = cfg.title_band_ratio
        self.sidebar_x_ratio = cfg.sidebar_x_ratio
        self.max_clean_text_chars = cfg.max_clean_text_chars
        self.extra_noise_patterns = cfg.extra_noise_patterns

    def decompose(self, raw_boxes: list, img_width: int, img_height: int) -> dict:
        """
        Args:
            raw_boxes: list of ``(polygon_pts, text, score)`` tuples/lists,
                where ``polygon_pts`` is ``[[x1,y1],[x2,y2],[x3,y3],[x4,y4]]``.
            img_width: frame pixel width.
            img_height: frame pixel height.

        Returns:
            ``{"titles": [...], "content": [...], "details": [...], "flat_text": str}``
        """
        if not raw_boxes or img_width <= 0 or img_height <= 0:
            return dict(_EMPTY_SPATIAL_RESULT)

        parsed_boxes = []
        heights = []

        for item in raw_boxes:
            if not item or len(item) < 2:
                continue
            poly, text = item[0], item[1]
            if not text or not str(text).strip():
                continue

            clean_t = clean_ocr_text(
                str(text),
                extra_noise_patterns=self.extra_noise_patterns,
                max_chars=self.max_clean_text_chars,
            )
            if not clean_t:
                continue

            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)

            nx = (x_min + x_max) / (2.0 * img_width)
            ny = (y_min + y_max) / (2.0 * img_height)
            nh = max((y_max - y_min) / float(img_height), 0.001)

            # Perimeter rejection: OS taskbar / browser chrome.
            if ny < self.top_cut or ny > (1.0 - self.bottom_cut):
                continue

            parsed_boxes.append({"text": clean_t, "nx": nx, "ny": ny, "nh": nh})
            heights.append(nh)

        if not parsed_boxes:
            return dict(_EMPTY_SPATIAL_RESULT)

        # Statistical percentile-based font-size hierarchy (resolution-independent).
        sorted_heights = sorted(heights)
        med_h = sorted_heights[len(sorted_heights) // 2]
        title_h_thresh = max(med_h * self.title_height_multiplier, self.title_height_floor)
        detail_h_thresh = med_h * self.detail_height_multiplier

        titles, content, details = [], [], []
        for b in parsed_boxes:
            t, nh, nx, ny = b["text"], b["nh"], b["nx"], b["ny"]
            if nh >= title_h_thresh or (ny < self.title_band_ratio and nh >= med_h):
                titles.append(t)
            elif nx < self.sidebar_x_ratio and nh <= detail_h_thresh:
                details.append(t)
            else:
                content.append(t)

        return {
            "titles": titles,
            "content": content,
            "details": details,
            "flat_text": " ".join(titles + content).strip(),
        }


class OCREngine:
    """Auto-fallback OCR backend wrapper. See module docstring for priority order."""

    def __init__(self, config: OCRConfig | None = None) -> None:
        self.config = config or OCRConfig()
        self.backend: str | None = None
        self.reader = None
        self.spatial_extractor = SpatialLayoutExtractor(self.config)
        force_backend = "none" if not self.config.enabled else self.config.backend
        self._init_engine(force_backend)

    def _init_engine(self, force_backend: str | None) -> None:
        backends_to_try = [force_backend] if force_backend else ["rapid", "paddle", "easy", "tesseract", "none"]
        for backend in backends_to_try:
            try:
                if backend == "rapid":
                    from rapidocr_onnxruntime import RapidOCR

                    self.reader = RapidOCR()
                    self.backend = "rapid"
                    logger.info("Using RapidOCR-ONNX backend")
                    return
                elif backend == "paddle":
                    from paddleocr import PaddleOCR

                    self.reader = PaddleOCR(use_angle_cls=False, lang="en", show_log=False, use_gpu=False)
                    self.backend = "paddle"
                    logger.info("Using PaddleOCR backend")
                    return
                elif backend == "easy":
                    import easyocr

                    self.reader = easyocr.Reader(["en"], gpu=False, verbose=False)
                    self.backend = "easy"
                    logger.info("Using EasyOCR backend")
                    return
                elif backend == "tesseract":
                    import pytesseract

                    pytesseract.get_tesseract_version()
                    self.reader = pytesseract
                    self.backend = "tesseract"
                    logger.info("Using Tesseract backend")
                    return
                elif backend == "none":
                    self.backend = "none"
                    logger.info("OCR disabled -- transcript-only mode")
                    return
            except Exception as exc:
                logger.debug("OCR backend %s unavailable (%s), trying next", backend, exc)
                continue
        self.backend = "none"
        logger.warning("No OCR backend available -- falling back to transcript-only mode")

    def extract_spatial(self, image_path: str) -> dict:
        """Extract the structured spatial hierarchy for one frame image."""
        if not image_path or not os.path.exists(image_path) or self.backend == "none":
            return dict(_EMPTY_SPATIAL_RESULT)

        try:
            from PIL import Image

            with Image.open(image_path) as img:
                width, height = img.size
        except Exception:
            width, height = 1920, 1080

        try:
            if self.backend == "rapid":
                result, _ = self.reader(image_path)
                if not result:
                    return dict(_EMPTY_SPATIAL_RESULT)
                return self.spatial_extractor.decompose(result, width, height)
            elif self.backend == "paddle":
                result = self.reader.ocr(image_path, cls=False)
                if not result or not result[0]:
                    return dict(_EMPTY_SPATIAL_RESULT)
                formatted = [[item[0], item[1][0], item[1][1]] for item in result[0] if len(item) > 1]
                return self.spatial_extractor.decompose(formatted, width, height)
            elif self.backend in ("easy", "tesseract"):
                # Flat-text fallback -- these backends don't return per-box
                # bounding polygons in a form we decompose spatially.
                flat = self.extract(image_path)
                return {"titles": [], "content": [flat] if flat else [], "details": [], "flat_text": flat}
        except Exception as exc:
            logger.debug("Spatial OCR failed for %s: %s", image_path, exc)
            return dict(_EMPTY_SPATIAL_RESULT)

        return dict(_EMPTY_SPATIAL_RESULT)

    def extract(self, image_path: str) -> str:
        """Legacy flat-string OCR extraction (no cleaning applied)."""
        if not image_path or not os.path.exists(image_path) or self.backend == "none":
            return ""

        try:
            if self.backend == "rapid":
                result, _ = self.reader(image_path)
                if not result:
                    return ""
                return " ".join(line[1] for line in result if len(line) >= 2)
            elif self.backend == "paddle":
                result = self.reader.ocr(image_path, cls=False)
                if not result or not result[0]:
                    return ""
                return " ".join(line[1][0] for line in result[0] if len(line) > 1)
            elif self.backend == "easy":
                return " ".join(self.reader.readtext(image_path, detail=0))
            elif self.backend == "tesseract":
                from PIL import Image

                return self.reader.image_to_string(Image.open(image_path), config="--psm 6")
        except Exception as exc:
            logger.debug("OCR extract failed for %s: %s", image_path, exc)
            return ""
        return ""
