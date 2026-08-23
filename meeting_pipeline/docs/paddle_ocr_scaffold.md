Yes, this pipeline is feasible with PaddleOCR:

[URL](https://www.perplexity.ai/search/991bdec8-f8cb-43dd-932a-69e8543c70d9#6)

```text
Image
  → layout detection
  → region filtering
  → crop each region
  → OCR each crop
  → spatial hierarchy construction
  → JSON validation/output
```

PaddleOCR’s newer APIs provide separate layout detection and OCR interfaces, and PP-StructureV3 follows a layout-first architecture with layout analysis, OCR, and post-processing stages. Its results can be serialized to JSON. [arxiv](https://arxiv.org/html/2507.05595v1)

I created a Python scaffold for you: **`paddleocr_layout_hierarchy_scaffold.py`**.

## What the scaffold does

It:

1. Loads an input image using OpenCV.
2. Runs PaddleOCR layout detection.
3. Normalizes layout results into internal region objects.
4. Filters low-confidence regions.
5. Crops text-oriented regions.
6. Runs PaddleOCR on each crop.
7. Converts crop-relative OCR boxes back to full-image coordinates.
8. Assigns regions to parent containers using spatial containment.
9. Sorts children approximately by reading order.
10. Writes versioned hierarchical JSON.

Run it like this:

```bash
python paddleocr_layout_hierarchy_scaffold.py \
  screenshot.png \
  --output parsed.json
```

## Install

For a basic CPU setup:

```bash
python -m venv .venv
source .venv/bin/activate

pip install -U pip
pip install paddlepaddle paddleocr opencv-python
```

For GPU, install the PaddlePaddle build matching your CUDA version first, then install PaddleOCR. PaddleOCR’s model weights are downloaded automatically on first use, but for production you should pin model versions and use explicit model directories. [arxiv](https://arxiv.org/html/2507.05595v1)

## Expected JSON shape

The scaffold produces output broadly like:

```json
{
  "schema_version": "0.1.0",
  "source": {
    "path": "screenshot.png",
    "width": 1920,
    "height": 1080
  },
  "pipeline": {
    "layout_model": "PaddleOCR LayoutDetection",
    "ocr_model": "PaddleOCR",
    "min_layout_score": 0.35
  },
  "document": {
    "id": "page_0",
    "type": "page",
    "bbox": [0, 0, 1920, 1080],
    "children": [
      {
        "id": "region_a",
        "type": "text_block",
        "bbox": [100, 120, 900, 300],
        "confidence": 0.94,
        "text": "Detected text...",
        "text_confidence": 0.97,
        "parent_id": "page_0"
      }
    ]
  }
}
```

## Important limitation

PaddleOCR’s standard layout models are primarily trained for **document layouts**: titles, paragraphs, tables, figures, headers, footers, formulas, charts, and related regions. The documented layout categories are not a complete taxonomy for browser or desktop UI elements. [paddlepaddle.github](https://paddlepaddle.github.io/PaddleX/3.1/en/module_usage/tutorials/ocr_modules/layout_detection.html)

Therefore, for your screen-share use case, the scaffold is a good structural baseline, but you will eventually need additional UI-specific components:

```text
Paddle layout detection
  → document-like regions

UI/icon detector
  → tabs, buttons, speaker icons, folders, controls

PaddleOCR
  → text inside each detected region

Hierarchy builder
  → spatial relationships and parent-child structure
```

## Recommended next improvements

### 1. Add layout overlays

Before trusting the hierarchy, draw every detected region and label on the original image:

```text
region box + class + confidence + ID
```

This is essential for debugging false detections and wrong hierarchy assignments.

### 2. Add a dedicated icon/UI detector

PaddleOCR layout detection may not reliably detect:

- Speaker icons.
- Microphone buttons.
- Browser tabs.
- Folder icons.
- Toolbar controls.
- Participant tiles.

Add a UI detector such as OmniParser or a custom YOLO/RT-DETR model, then merge its results with PaddleOCR regions.

### 3. Improve hierarchy construction

The current scaffold uses simple bounding-box containment:

```text
if region A contains region B:
    A becomes a possible parent of B
```

For real screens, add:

- Horizontal and vertical alignment.
- Indentation.
- Separator lines.
- Icon-text proximity.
- Repeated row detection.
- Region overlap rules.
- Application-window grouping.
- Confidence-based parent selection.

A folder tree, for example, should use indentation and connector lines—not just containment.

### 4. Use region-specific OCR settings

Different crops may require different processing:

```text
small UI label       → upscaling + textline orientation
table                → table recognition
formula              → formula recognition
dense paragraph      → standard OCR
vertical text        → orientation-aware OCR
```

Do not use one OCR configuration blindly for every region.

### 5. Add a semantic enrichment stage

After OCR and layout construction, pass the candidate JSON to a VLM only for semantic interpretation:

```text
Detected candidates + OCR + geometry
              ↓
VLM
              ↓
roles, states, relationships, corrected hierarchy
```

For example:

```json
{
  "task": "classify_ui_relationships",
  "elements": [
    {
      "id": "e1",
      "text": "src",
      "bbox": [30, 300, 80, 325],
      "detected_type": "text"
    },
    {
      "id": "e2",
      "text": "components",
      "bbox": [55, 335, 150, 360],
      "detected_type": "text"
    }
  ]
}
```

The VLM can return:

```json
{
  "relationships": [
    {
      "type": "child_of",
      "source": "e2",
      "target": "e1"
    }
  ],
  "updates": [
    {
      "id": "e1",
      "type": "folder",
      "expanded": true
    },
    {
      "id": "e2",
      "type": "folder",
      "expanded": false
    }
  ]
}
```

Keep OCR as the authoritative source for exact text and use the VLM for interpretation.

## Suggested service structure

Once the script works, refactor it into:

```text
app/
├── main.py
├── schemas.py
├── providers/
│   ├── paddle_layout.py
│   ├── paddle_ocr.py
│   └── ui_detector.py
├── hierarchy/
│   ├── containment.py
│   ├── reading_order.py
│   └── relationships.py
├── enrichment/
│   └── vlm.py
└── validation/
    └── json_schema.py
```

Expose:

```text
POST /v1/parse
POST /v1/parse/async
GET  /v1/jobs/{job_id}
```

Keep the public schema independent of PaddleOCR’s native response. PaddleOCR result formats and model names can evolve; your client-facing JSON contract should not.

The scaffold gives you the first working stage. The next meaningful milestone is to add visual overlays, test it on 20–30 representative images, and measure whether layout boxes, OCR text, and parent-child assignments are correct before introducing VLM enrichment.