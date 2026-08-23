"""Default `KeywordExtractor` implementation, backed by YAKE.

Port reference: the `yake.KeywordExtractor(...)` construction +
`.extract_keywords(...)` calls in both
`meeting_pipeline/context_builder.py::__init__` and
`meeting_pipeline/document_aligner.py::__init__`/`_extract_keywords()` --
again, one implementation instead of two near-identical ones.

Both original call sites wrap extraction in a try/except and degrade to an
empty keyword list on failure (unavailable package, extraction error on
pathological input) -- preserve that graceful-degradation behavior here so
neither stage needs its own fallback handling.
"""

from __future__ import annotations

from ..core.interfaces import KeywordExtractor


class YakeKeywordExtractor(KeywordExtractor):
    """YAKE-backed keyword extractor with graceful degradation if YAKE is
    unavailable or extraction fails on a given input.

    TODO: lazily import `yake` in `__init__`; catch import/construction
    failure and set an internal "disabled" flag so `extract()` just returns
    `[]` rather than raising, matching the original's degrade-don't-crash
    behavior.
    """

    def __init__(self, *, ngram_size: int = 2, top_n: int = 10) -> None:
        self.ngram_size = ngram_size
        self.top_n = top_n
        self._extractor = None  # lazy-loaded; None also means "disabled"

    def extract(self, text: str) -> list[str]:
        raise NotImplementedError
