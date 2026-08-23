"""Default local `EmbeddingProvider` implementation, backed by
sentence-transformers.

Port reference: the `SentenceTransformer(...)` construction + `.encode(...)`
calls in `meeting_pipeline/context_builder.py::__init__`/`build_topics()` and
`meeting_pipeline/document_aligner.py::__init__`/`align()`. Both call sites
in the original construct their own model instance with duplicated
device/batch-size handling; here there is exactly one implementation,
constructed once (see `config/schema.py::EmbeddingConfig`) and injected into
whichever stage needs it.

Import `sentence_transformers` lazily inside `__init__`/`encode`, not at
module top -- consistent with the package-wide rule that heavy dependencies
only load when actually used.
"""

from __future__ import annotations

from ..config.schema import EmbeddingConfig
from ..core.interfaces import EmbeddingProvider


class SentenceTransformerProvider(EmbeddingProvider):
    """Local sentence-transformers-backed embedding provider.

    TODO:
      - lazily import + construct `SentenceTransformer(model_name, device=...)`
        in `__init__`, caching the instance on `self`.
      - `encode()`: call `self._model.encode(texts, batch_size=...,
        normalize_embeddings=True, convert_to_numpy=True)` and return as
        `list[list[float]]` (or keep numpy internally -- decide based on what
        `stages/context` and `stages/align` actually need, since both
        currently do `np.dot` on the raw arrays).
    """

    def __init__(self, config: EmbeddingConfig) -> None:
        self.config = config
        self._model = None  # lazy-loaded

    def encode(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError
