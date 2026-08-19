"""Text-normalization and OCR noise-cleaning utilities.

``clean_ocr_text`` strips the kind of screen-recording noise that shows up in
OCR output regardless of platform: file-path breadcrumbs, OS taskbar
clocks/weather/battery indicators, meeting-app chrome ("Microsoft Teams",
"Zoom Meeting", ...), and browser/Streamlit UI boilerplate.

Two patterns present in the original implementation have been removed rather
than ported: a regex hardcoding a handful of specific contributors' real
names, and a regex stripping avatar-badge initials (``SR``/``MD``/``PR``
followed by a word). Both were debug artifacts left over from cleaning one
contributor's own screen recordings, not general requirements -- and the
initials regex in particular incidentally strips legitimate engineering text
like "PR review" or "MD file". The general mechanism for the underlying
problem (a recurring on-screen name/label) already exists downstream:
``context_builder.py``'s meeting-wide
document-frequency filter strips any OCR token that appears on more than
``ContextConfig.boilerplate_document_frequency`` of a meeting's frames, which
catches a recurring participant name without hardcoding it. If you need the
old initials-stripping behavior for your own recordings, pass it via
``extra_noise_patterns`` -- see docs/ocr_backends.md for the exact pattern.
"""

from __future__ import annotations

import re
from typing import Sequence

_WHITESPACE_RE = re.compile(r"\s+")
_ALPHA_WORD_RE = re.compile(r"[A-Za-z]{3,}")
_ALNUM_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")

# Applied in order. Each strips one category of screen-recording noise.
_NOISE_PATTERNS: tuple[tuple[str, int], ...] = (
    # 1. File paths, breadcrumbs, drive letters (e.g. C:\Users\... or a > b > c)
    (r"\b[A-Za-z]:\\[^ \n\t]+\b", 0),
    (r"\b(?:/[a-zA-Z0-9._-]+){2,}\b", 0),
    (r"\b[a-zA-Z_0-9]+(?:\s*>\s*[a-zA-Z_0-9]+){2,}\b", 0),
    # 2. System taskbar clocks, battery, weather, and date metrics
    (r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|UTC)?\b", re.IGNORECASE),
    (r"\b\d{1,2}[\u00b0]?\s*(?:ENG|IN|US|UK)?\b", 0),
    (r"\b\d{1,3}%\s*(?:IN|US)?\b", 0),
    (r"\b(?:Mostly cloudy|Partly cloudy|Cloudy|Sunny|Rainy|Clear)\b", re.IGNORECASE),
    (r"\b\d{2}-[A-Za-z]{3}-\d{2,4}\b", 0),
    (r"\b\d{4}-\d{2}-\d{2}\b", 0),
    (r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", 0),
    # 3. Meeting platform chrome
    (
        r"\b(?:Microsoft Teams|Zoom Meeting|Google Meet|Webex|Recorded automatically|"
        r"Share this window|Stop sharing)\b",
        re.IGNORECASE,
    ),
    # 4. Web browser, Streamlit framework boilerplate & file explorer metadata
    (r"\b(?:https?://|localhost:\d+)\S*\b", re.IGNORECASE),
    (r"\b(?:Deploy|Navigation&Filters|Navigation Filters|Navigation|Filters)\b", 0),
    (
        r"\b(?:Select Account|Select Project|Select Meeting|Select singlefile to get more)\b",
        re.IGNORECASE,
    ),
    (
        r"\b(?:RawTranscript&PresentationSlidesLibrary|PresentationSlidesLibrary|"
        r"RawTranscript|Presentation SlidesLibrary)\b",
        0,
    ),
    (
        r"\b(?:Totalrawtranscriptsegments:\d+|Total presentationslidesfound:\d+|"
        r"Totalrawtranscript segments:\d+|Totalpresentationslidesfound:\d+)\b",
        0,
    ),
    (
        r"\b(?:Search&FilterRawTranscript|Search&Filter RawTranscript|Search&Filter|Search \S+)\b",
        re.IGNORECASE,
    ),
    (
        r"\b(?:File folder|Date modified|Size:\s*\d+(?:\.\d+)?\s*(?:KB|MB|GB)?|"
        r"Type File folder|\d+\s*items(?:\s*\d+\s*item\s*selected)?)\b",
        re.IGNORECASE,
    ),
)
_COMPILED_NOISE_PATTERNS = [re.compile(p, flags) for p, flags in _NOISE_PATTERNS]

_NON_PRINTABLE_RE = re.compile(r"[^\x20-\x7E\u00A0-\u00FF]+")


def normalize_whitespace(text: str | None) -> str:
    """Collapse runs of whitespace to a single space and strip the ends."""
    if not text:
        return ""
    return _WHITESPACE_RE.sub(" ", str(text)).strip()


def is_meaningful_text(text: str | None) -> bool:
    """Quality gate: does this look like human-readable content, not UI noise?

    Requires at least 15 characters, a letter ratio of at least 60%, and at
    least 3 alphabetic words of length >= 3.
    """
    if not text:
        return False
    t = text.strip()
    if len(t) < 15:
        return False
    letters = sum(1 for c in t if c.isalpha())
    total = len(t)
    if total == 0 or (letters / total) < 0.60:
        return False
    words = _ALPHA_WORD_RE.findall(t)
    return len(words) >= 3


def clean_ocr_text(
    text: str | None,
    extra_noise_patterns: Sequence[str] = (),
    max_chars: int = 5000,
) -> str:
    """Strip screen-recording UI noise from raw OCR text.

    Returns ``""`` if the cleaned result fails the :func:`is_meaningful_text`
    quality gate (i.e. it was mostly noise to begin with).

    Args:
        text: raw OCR output for one frame/box.
        extra_noise_patterns: additional regexes to strip, applied after the
            built-in set. Use this to add recording-specific noise (e.g.
            recurring avatar-badge initials) without modifying this module.
        max_chars: cap on the returned string length.
    """
    if not text:
        return ""
    t = str(text)
    for pattern in _COMPILED_NOISE_PATTERNS:
        t = pattern.sub(" ", t)
    for pattern in extra_noise_patterns:
        t = re.sub(pattern, " ", t)
    t = _NON_PRINTABLE_RE.sub(" ", t)
    t = _WHITESPACE_RE.sub(" ", t).strip()
    tokens = [tok for tok in t.split() if len(tok) >= 2 or tok.isalnum()]
    cleaned = " ".join(tokens).strip()
    return cleaned[:max_chars] if is_meaningful_text(cleaned) else ""


def token_set(text: str) -> set[str]:
    """Lowercased set of alphanumeric tokens with length >= 3."""
    return {w for w in _ALNUM_TOKEN_RE.findall(text.lower()) if len(w) >= 3}
