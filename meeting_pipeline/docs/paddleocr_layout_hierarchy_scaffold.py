"""PaddleOCR layout-first hierarchical JSON scaffold.

Pipeline:
    image -> layout detection -> region crops -> OCR per region
          -> spatial hierarchy -> versioned JSON

This scaffold targets document-like images and can be extended with a UI/icon
provider later. PaddleOCR model/result fields can vary across releases, so the
normalization helpers intentionally accept common result shapes.
"""

from __future__ import annotations

import argparse
import json
import math
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

import cv2
from paddleocr import LayoutDetection, PaddleOCR


@dataclass
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    def clip(self, width: int, height: int, pad: int = 4) -> "BBox":
        return BBox(
            max(0, self.x1 - pad),
            max(0, self.y1 - pad),
            min(width, self.x2 + pad),
            min(height, self.y2 + pad),
        )

    def to_list(self) -> list[float]:
        return [round(v, 2) for v in (self.x1, self.y1, self.x2, self.y2)]


@dataclass
class Region:
    id: str
    type: str
    bbox: BBox
    confidence: float
    order: int = 0
    parent_id: str | None = None
    text: str | None = None
    text_confidence: float | None = None
    children: list["Region"] = field(default_factory=list)


# Paddle layout labels vary by model/version. Adjust this mapping for your data.
LAYOUT_LABEL_MAP = {
    "text": "text_block",
    "paragraph": "text_block",
    "title": "title",
    "doc_title": "title",
    "paragraph_title": "heading",
    "table": "table",
    "figure": "figure",
    "image": "image",
    "chart": "chart",
    "formula": "formula",
    "header": "header",
    "footer": "footer",
    "list": "list",
    "sidebar_text": "sidebar",
}


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def as_plain(value: Any) -> Any:
    """Convert Paddle result wrappers / numpy values into JSON-compatible data."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "tolist"):
        return as_plain(value.tolist())
    if isinstance(value, dict):
        return {str(k): as_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [as_plain(v) for v in value]
    if hasattr(value, "json"):
        try:
            return as_plain(value.json)
        except Exception:
            pass
    return value


def result_dict(result: Any) -> dict[str, Any]:
    """Extract a PaddleOCR/PaddleX result into a plain dictionary."""
    result = as_plain(result)
    if isinstance(result, dict):
        return result
    return {}


def first_value(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def normalize_box(raw: Any) -> BBox | None:
    """Accept [x1,y1,x2,y2], 4 points, or Paddle-style polygon boxes."""
    raw = as_plain(raw)
    if not raw:
        return None
    if isinstance(raw, (list, tuple)) and len(raw) == 4:
        if all(isinstance(v, (int, float)) for v in raw):
            return BBox(float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))
        if all(isinstance(p, (list, tuple)) and len(p) >= 2 for p in raw):
            xs = [float(p[0]) for p in raw]
            ys = [float(p[1]) for p in raw]
            return BBox(min(xs), min(ys), max(xs), max(ys))
    return None


def extract_layout_items(raw_result: Any) -> list[dict[str, Any]]:
    """Normalize common layout-result formats into label/score/box records."""
    data = result_dict(raw_result)
    candidates = first_value(data, "boxes", "layout_res", "layout", "predictions")
    if candidates is None and isinstance(data.get("res"), dict):
        candidates = first_value(data["res"], "boxes", "layout_res", "layout")
    if isinstance(candidates, dict):
        candidates = [candidates]
    if not isinstance(candidates, list):
        return []

    items = []
    for item in candidates:
        item = as_plain(item)
        if not isinstance(item, dict):
            continue
        box = normalize_box(first_value(item, "coordinate", "bbox", "box", "points"))
        if box is None:
            continue
        label = str(first_value(item, "label", "type", "class_name") or "region")
        score = float(first_value(item, "score", "confidence", "prob") or 0.0)
        items.append({"label": label, "score": score, "bbox": box})
    return items


def extract_ocr_lines(raw_result: Any) -> list[dict[str, Any]]:
    """Normalize common PaddleOCR OCR-result formats."""
    data = result_dict(raw_result)
    res = data.get("res", data)
    if not isinstance(res, dict):
        return []

    texts = first_value(res, "rec_texts", "texts") or []
    scores = first_value(res, "rec_scores", "scores") or []
    boxes = first_value(res, "rec_polys", "rec_boxes", "dt_polys", "boxes") or []

    lines = []
    for i, text in enumerate(texts):
        box = normalize_box(boxes[i]) if i < len(boxes) else None
        if box is None:
            continue
        score = float(scores[i]) if i < len(scores) else 0.0
        lines.append({"text": str(text), "confidence": score, "bbox": box})
    return lines


def intersection_over_region(line: BBox, region: BBox) -> float:
    x1, y1 = max(line.x1, region.x1), max(line.y1, region.y1)
    x2, y2 = min(line.x2, region.x2), min(line.y2, region.y2)
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    return intersection / max(line.area, 1.0)


def sort_lines(lines: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(lines, key=lambda x: (x["bbox"].y1, x["bbox"].x1))


def ocr_region(
    ocr: PaddleOCR,
    image,
    region: Region,
    pad: int = 4,
) -> None:
    height, width = image.shape[:2]
    crop_box = region.bbox.clip(width, height, pad)
    crop = image[int(crop_box.y1):int(crop_box.y2), int(crop_box.x1):int(crop_box.x2)]
    if crop.size == 0:
        return

    result = next(iter(ocr.predict(crop)), None)
    lines = extract_ocr_lines(result)
    if not lines:
        return

    # OCR boxes are relative to the crop; shift them back to page coordinates.
    for line in lines:
        b = line["bbox"]
        line["bbox"] = BBox(
            b.x1 + crop_box.x1,
            b.y1 + crop_box.y1,
            b.x2 + crop_box.x1,
            b.y2 + crop_box.y1,
        )

    lines = sort_lines(lines)
    region.text = "\n".join(line["text"] for line in lines)
    region.text_confidence = sum(line["confidence"] for line in lines) / len(lines)


def contains(outer: BBox, inner: BBox, tolerance: float = 8.0) -> bool:
    return (
        outer.x1 - tolerance <= inner.x1
        and outer.y1 - tolerance <= inner.y1
        and outer.x2 + tolerance >= inner.x2
        and outer.y2 + tolerance >= inner.y2
    )


def build_hierarchy(regions: list[Region]) -> Region:
    root = Region(
        id="page_0",
        type="page",
        bbox=BBox(0, 0, 0, 0),
        confidence=1.0,
    )
    for region in sorted(regions, key=lambda r: (r.bbox.y1, r.bbox.x1)):
        possible_parents = [
            p for p in regions
            if p is not region and contains(p.bbox, region.bbox)
            and p.bbox.area > region.bbox.area
        ]
        parent = min(possible_parents, key=lambda p: p.bbox.area, default=root)
        region.parent_id = parent.id
        parent.children.append(region)

    def sort_tree(node: Region) -> None:
        node.children.sort(key=lambda r: (r.bbox.y1, r.bbox.x1))
        for child in node.children:
            sort_tree(child)

    sort_tree(root)
    return root


def region_to_json(region: Region) -> dict[str, Any]:
    output = {
        "id": region.id,
        "type": region.type,
        "bbox": region.bbox.to_list(),
        "confidence": round(region.confidence, 4),
        "order": region.order,
        "parent_id": region.parent_id,
    }
    if region.text is not None:
        output["text"] = region.text
        output["text_confidence"] = round(region.text_confidence or 0.0, 4)
    if region.children:
        output["children"] = [region_to_json(child) for child in region.children]
    return output


def parse_image(image_path: str, output_path: str, min_layout_score: float = 0.35) -> dict[str, Any]:
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")
    height, width = image.shape[:2]

    # PaddleOCR downloads model weights on first use. Pin/model-dir these in production.
    layout_model = LayoutDetection()
    ocr = PaddleOCR(
        lang="en",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=True,
    )

    layout_result = next(iter(layout_model.predict(image)), None)
    layout_items = extract_layout_items(layout_result)
    layout_items = [x for x in layout_items if x["score"] >= min_layout_score]

    regions: list[Region] = []
    for index, item in enumerate(layout_items):
        label = item["label"].lower().replace(" ", "_")
        region = Region(
            id=new_id("region"),
            type=LAYOUT_LABEL_MAP.get(label, label),
            bbox=item["bbox"],
            confidence=item["score"],
            order=index,
        )
        # OCR only regions likely to contain text. Add UI/icon classes here later.
        if region.type in {"text_block", "title", "heading", "header", "footer", "sidebar", "list"}:
            ocr_region(ocr, image, region)
        regions.append(region)

    root = build_hierarchy(regions)
    root.bbox = BBox(0, 0, width, height)

    payload = {
        "schema_version": "0.1.0",
        "source": {
            "path": str(image_path),
            "width": width,
            "height": height,
        },
        "pipeline": {
            "layout_model": "PaddleOCR LayoutDetection",
            "ocr_model": "PaddleOCR",
            "min_layout_score": min_layout_score,
        },
        "document": region_to_json(root),
    }
    Path(output_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="Input image path")
    parser.add_argument("--output", default="parsed.json")
    parser.add_argument("--min-layout-score", type=float, default=0.35)
    args = parser.parse_args()
    parse_image(args.image, args.output, args.min_layout_score)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
