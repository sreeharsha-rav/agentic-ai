"""Text-normalization and OCR noise-cleaning utilities.

Port reference: `meeting_pipeline/text_cleaning.py` in full -- the
noise-pattern regex table (file paths, taskbar clocks, meeting-app chrome,
browser boilerplate), `normalize_whitespace`, `is_meaningful_text`,
`clean_ocr_text`, and `token_set`. Deliberately does NOT port the two
patterns the original already removed (hardcoded contributor names / avatar
initials) -- see that module's docstring for why, and use
`OCRConfig.extra_noise_patterns` (once `config/schema.py`'s `OCRConfig` is
fleshed out) for recording-specific noise instead.
"""

from __future__ import annotations

from typing import Sequence


def normalize_whitespace(text: str | None) -> str:
    """Collapse runs of whitespace to a single space and strip the ends.

    TODO: port from `text_cleaning.py::normalize_whitespace()`.
    """
    raise NotImplementedError


def is_meaningful_text(text: str | None) -> bool:
    """Quality gate: does this look like human-readable content, not UI noise?

    TODO: port from `text_cleaning.py::is_meaningful_text()`.
    """
    raise NotImplementedError


def clean_ocr_text(
    text: str | None,
    extra_noise_patterns: Sequence[str] = (),
    max_chars: int = 5000,
) -> str:
    """Strip screen-recording UI noise from raw OCR text.

    TODO: port from `text_cleaning.py::clean_ocr_text()`.
    """
    raise NotImplementedError


def token_set(text: str) -> set[str]:
    """Lowercased set of alphanumeric tokens with length >= 3.

    TODO: port from `text_cleaning.py::token_set()`.
    """
    raise NotImplementedError
