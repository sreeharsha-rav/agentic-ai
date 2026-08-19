"""Tests for SpatialLayoutExtractor. Runs with zero third-party packages
installed, thanks to ocr_engine.py's no-module-level-third-party-imports rule.
"""

from __future__ import annotations

from meeting_pipeline.config import OCRConfig
from meeting_pipeline.ocr_engine import SpatialLayoutExtractor

IMG_W, IMG_H = 1920, 1080


def _box(x0: float, y0: float, x1: float, y1: float, text: str):
    poly = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
    return (poly, text, 0.99)


def test_decompose_empty_input():
    extractor = SpatialLayoutExtractor()
    result = extractor.decompose([], IMG_W, IMG_H)
    assert result == {"titles": [], "content": [], "details": [], "flat_text": ""}


def test_decompose_zero_dimensions():
    extractor = SpatialLayoutExtractor()
    boxes = [_box(0, 0, 100, 40, "Some meaningful heading text here")]
    result = extractor.decompose(boxes, 0, IMG_H)
    assert result["titles"] == []


def test_decompose_rejects_top_and_bottom_margins():
    extractor = SpatialLayoutExtractor()
    # A box centred in the top 3% (browser chrome / URL bar) is dropped.
    top_chrome = _box(0, 0, 400, int(IMG_H * 0.02), "This meaningful text lives in browser chrome")
    # A box centred in the bottom 7% (OS taskbar) is dropped.
    bottom_chrome = _box(0, int(IMG_H * 0.98), 400, IMG_H, "This meaningful text lives in the taskbar")
    result = extractor.decompose([top_chrome, bottom_chrome], IMG_W, IMG_H)
    assert result == {"titles": [], "content": [], "details": [], "flat_text": ""}


def test_decompose_crop_margins_disabled_keeps_perimeter_boxes():
    cfg = OCRConfig(crop_margins=False)
    extractor = SpatialLayoutExtractor(cfg)
    top_chrome = _box(0, 0, 400, int(IMG_H * 0.02), "This meaningful text lives in browser chrome")
    result = extractor.decompose([top_chrome], IMG_W, IMG_H)
    assert result["flat_text"] != ""


def test_decompose_large_font_becomes_title():
    extractor = SpatialLayoutExtractor()
    # A large-height box (way above median) becomes a title; a mid-canvas
    # box of typical height becomes content.
    boxes = [
        _box(600, 500, 1300, 540, "Typical body content sentence about the roadmap plan"),
        _box(600, 100, 1300, 260, "A Very Large Prominent Heading About Architecture"),
    ]
    result = extractor.decompose(boxes, IMG_W, IMG_H)
    assert any("Prominent Heading" in t for t in result["titles"])
    assert any("body content sentence" in c for c in result["content"])


def test_decompose_top_banner_zone_becomes_title_even_at_median_height():
    extractor = SpatialLayoutExtractor()
    # Two boxes of identical (median) height: one in the top banner zone
    # (ny < title_band_ratio) becomes a title via the banner rule; the other,
    # at mid-canvas, becomes content.
    banner = _box(600, 60, 1300, 100, "Banner Zone Heading About The Quarterly Roadmap")
    body = _box(600, 500, 1300, 540, "Mid canvas body sentence about the quarterly roadmap plan")
    result = extractor.decompose([banner, body], IMG_W, IMG_H)
    assert any("Banner Zone Heading" in t for t in result["titles"])
    assert any("Mid canvas body sentence" in c for c in result["content"])


def test_decompose_small_left_column_becomes_details():
    extractor = SpatialLayoutExtractor()
    boxes = [
        _box(600, 500, 1300, 540, "Typical body content sentence about the roadmap plan"),
        # Small font, far-left column (sidebar navigation label).
        _box(10, 500, 200, 512, "File Explorer Navigation Label Item"),
    ]
    result = extractor.decompose(boxes, IMG_W, IMG_H)
    assert any("File Explorer Navigation" in d for d in result["details"])


def test_decompose_flat_text_is_titles_then_content():
    extractor = SpatialLayoutExtractor()
    boxes = [
        _box(600, 500, 1300, 540, "Typical body content sentence about the roadmap plan"),
        _box(600, 100, 1300, 260, "A Very Large Prominent Heading About Architecture"),
    ]
    result = extractor.decompose(boxes, IMG_W, IMG_H)
    assert result["flat_text"] == " ".join(result["titles"] + result["content"])


def test_decompose_excludes_boxes_that_fail_the_quality_gate():
    extractor = SpatialLayoutExtractor()
    # Fails is_meaningful_text (too short / not enough real words) and must
    # be excluded entirely rather than appearing as an empty-string entry.
    boxes = [_box(600, 500, 700, 540, "12:34")]
    result = extractor.decompose(boxes, IMG_W, IMG_H)
    assert result == {"titles": [], "content": [], "details": [], "flat_text": ""}


def test_decompose_malformed_items_are_skipped_not_fatal():
    extractor = SpatialLayoutExtractor()
    boxes = [
        None,
        ([[0, 0]],),  # too short (len < 2)
        _box(600, 500, 1300, 540, ""),  # empty text
        _box(600, 500, 1300, 540, "A perfectly normal meaningful sentence about caching"),
    ]
    result = extractor.decompose(boxes, IMG_W, IMG_H)
    assert any("caching" in c for c in result["content"])
