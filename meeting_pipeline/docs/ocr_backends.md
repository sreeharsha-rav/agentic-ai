# OCR Backends

`OCREngine` auto-detects a backend at construction time, trying each in
priority order and using the first one that imports and initializes
successfully:

| Priority | Backend | Package | Speed | Spatial hierarchy? | Notes |
|---|---|---|---|---|---|
| 1 | RapidOCR | `rapidocr-onnxruntime` | ~0.15s/frame | Yes | **Recommended default** for Windows/Linux. |
| 2 | PaddleOCR | `paddleocr` + `paddlepaddle` | moderate | Yes | Good alternative, works well on macOS. |
| 3 | EasyOCR | `easyocr` | ~1.5s/frame | No (flat text only) | Heaviest, but the most portable fallback. |
| 4 | Tesseract | `pytesseract` + the Tesseract binary | fast | No (flat text only) | Lightest Python dependency, but needs a separate system install. |
| 5 | None | -- | -- | -- | Transcript-only context; the pipeline still runs. |

Only RapidOCR and PaddleOCR return per-box bounding polygons, which is what
`SpatialLayoutExtractor` needs to build the titles/content/details hierarchy
(see `docs/architecture.md`). EasyOCR and Tesseract only return flat text, so
`OCREngine.extract_spatial()` falls back to putting everything in `content`
for those backends.

## Installing a backend

```bash
pip install -e ".[ocr]"        # = rapidocr-onnxruntime
pip install -e ".[easyocr]"
pip install -e ".[paddleocr]"  # also needs: pip install paddlepaddle
pip install -e ".[tesseract]"  # also needs the Tesseract binary:
                                #   Windows: winget install UB-Mannheim.TesseractOCR
                                #   macOS:   brew install tesseract
                                #   Linux:   apt install tesseract-ocr
```

Force a specific backend instead of auto-detection:

```python
from meeting_pipeline import PipelineConfig, OCRConfig

config = PipelineConfig(ocr=OCRConfig(backend="easy"))
```

Or via the CLI: `--ocr-backend easy`.

## Cleaning up OCR noise: `extra_noise_patterns`

`clean_ocr_text()` strips common screen-recording noise -- file-path
breadcrumbs, OS taskbar clocks/weather/battery, meeting-app chrome
("Microsoft Teams", "Zoom Meeting", ...), browser/Streamlit UI boilerplate --
by default. It deliberately does **not** hardcode any contributor's name or
initials: an earlier, pre-packaging version of this cleaning logic did, which
also had the side effect of stripping legitimate engineering text like
"PR review" or "MD file" whenever those two-letter tokens happened to appear.

If your own recordings have a recurring, predictable noise pattern (e.g. an
avatar badge that always renders as two initials followed by a name), add it
via `OCRConfig.extra_noise_patterns` instead of modifying the package:

```python
from meeting_pipeline import PipelineConfig, OCRConfig

config = PipelineConfig(
    ocr=OCRConfig(
        extra_noise_patterns=(
            r"\b(?:SR|MD|PR)\s+[A-Za-z.]+\b",  # example: avatar-badge initials + name
        )
    )
)
```

Note the general mechanism for the more common case -- a recurring
participant name or app title showing up across many frames -- is already
handled automatically: `MeetingContextBuilder`'s meeting-wide
document-frequency filter (`ContextConfig.boilerplate_document_frequency`)
strips any OCR token that appears on more than 65% of a meeting's frames,
without needing to know what that token is in advance.

## Spatial layout tuning

If your recordings use unusually small or large fonts, or an unusual
side-panel layout, the percentile/position thresholds in
`SpatialLayoutExtractor` are all configurable via `OCRConfig` -- see
`docs/configuration.md`'s `ocr` section for `title_height_multiplier`,
`detail_height_multiplier`, `title_band_ratio`, `sidebar_x_ratio`, and the
margin-crop fields.
