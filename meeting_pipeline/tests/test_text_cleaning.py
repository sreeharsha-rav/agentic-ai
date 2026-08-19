from __future__ import annotations

import inspect
import re

from meeting_pipeline import text_cleaning
from meeting_pipeline.text_cleaning import clean_ocr_text, is_meaningful_text, normalize_whitespace, token_set


def test_regression_no_personal_names_in_source():
    """Permanent tripwire: the old personal-recording debug cruft must never come back."""
    source = inspect.getsource(text_cleaning)
    for leaked in ("Rikita", "Sreeharsha", "Mayank"):
        assert leaked not in source, f"leaked personal name found in text_cleaning.py: {leaked}"


def test_normalize_whitespace():
    assert normalize_whitespace("a  \n b \t") == "a b"
    assert normalize_whitespace(None) == ""
    assert normalize_whitespace("") == ""


def test_is_meaningful_text():
    assert is_meaningful_text("") is False
    assert is_meaningful_text("short text!") is False  # < 15 chars
    assert is_meaningful_text("1234567890 !!! 000000") is False  # letter ratio < 0.60
    assert is_meaningful_text("ab cd ef gh ij kl") is False  # no words of length >= 3
    assert is_meaningful_text("This is a real sentence about architecture") is True


def test_clean_ocr_text_strips_file_paths_and_breadcrumbs():
    assert clean_ocr_text(r"open C:\Users\alice\project\file.py now") == ""
    result = clean_ocr_text("Navigate via Home > Documents > Reports then review the summary")
    assert "Home" not in result
    assert "review the summary" in result


def test_clean_ocr_text_strips_taskbar_clock_and_date():
    result = clean_ocr_text("The meeting started at 10:45 AM on 2026-08-18 to discuss the roadmap")
    assert "10:45" not in result
    assert "2026-08-18" not in result
    assert "roadmap" in result


def test_clean_ocr_text_strips_weather_and_platform_chrome():
    result = clean_ocr_text(
        "Mostly cloudy today while sharing on Microsoft Teams during the architecture review"
    )
    assert "Mostly cloudy" not in result
    assert "Microsoft Teams" not in result
    assert "architecture review" in result


def test_clean_ocr_text_strips_urls_and_localhost():
    result = clean_ocr_text("Visit https://example.com/docs or localhost:8501 for the live dashboard demo")
    assert "https://" not in result
    assert "localhost" not in result
    assert "live dashboard demo" in result


def test_clean_ocr_text_returns_empty_when_residue_is_not_meaningful():
    assert clean_ocr_text("10:45 AM 2026-08-18 https://x.co") == ""


def test_clean_ocr_text_truncates_and_respects_max_chars():
    long_text = "This is a long meaningful sentence about the system architecture. " * 200
    result = clean_ocr_text(long_text, max_chars=100)
    assert len(result) <= 100


def test_clean_ocr_text_extra_noise_patterns_opt_in():
    text = "SR reviewed the PR changes with MD file exported for the architecture discussion"
    # Default behavior: initials are no longer stripped (fix a2)
    default_result = clean_ocr_text(text)
    assert "PR" in default_result or "changes" in default_result

    # Opt back in via extra_noise_patterns for recordings that need it
    scrubbed = clean_ocr_text(text, extra_noise_patterns=(r"\b(?:SR|MD|PR)\s+[A-Za-z.]+\b",))
    assert "SR reviewed" not in scrubbed


def test_token_set():
    assert token_set("The API-v2 Gateway talks to Redis") == {
        "the",
        "api",
        "gateway",
        "talks",
        "redis",
    }
    assert token_set("") == set()


def test_noise_pattern_regexes_compile():
    # Guards against a typo silently breaking one of the built-in patterns.
    for pattern, flags in text_cleaning._NOISE_PATTERNS:
        re.compile(pattern, flags)
