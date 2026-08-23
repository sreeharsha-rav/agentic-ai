"""Topic-boundary detection: groups chronological speech segments into
topic clusters via three independent split conditions.

Port reference: `meeting_pipeline/context_builder.py::build_topics()`.
Isolated as its own module because it's a genuinely standalone algorithm
(temporal gap OR duration cap OR embedding cosine-drift) that only needs a
list of segment texts/timestamps and an optional `EmbeddingProvider` -- it
doesn't need to know anything about OCR or how segments were built,
making it directly unit-testable with plain segment fixtures and a fake
embedding provider.
"""

from __future__ import annotations

from ...core.interfaces import EmbeddingProvider
from ...core.models import Topic


def build_topics(
    segments: list,
    *,
    topic_gap_sec: float,
    max_topic_duration_sec: float,
    topic_similarity_threshold: float,
    min_segments_before_semantic_split: int,
    embedding_provider: EmbeddingProvider | None = None,
) -> list[list]:
    """Group segments into topic clusters.

    TODO: port from `context_builder.py::build_topics()`:
      1. If `embedding_provider` is given, batch-encode all segment texts.
      2. Per segment, check in order: gap-since-last > topic_gap_sec;
         cumulative duration > max_topic_duration_sec; (if embeddings
         available AND current topic has >= min_segments_before_semantic_split
         segments) cosine(seg_embedding, running_topic_centroid) <
         topic_similarity_threshold.
      3. On no split: fold the segment in and update the running centroid
         (`(mean * n + emb) / (n + 1)`, renormalized).
      4. Falls back to gap/duration-only splitting if `embedding_provider`
         is `None` (mirrors the original's graceful degradation when the
         embedding model fails to load).

    Returns lists of segments, one list per topic -- `service.py` is
    responsible for turning each into a `Topic` via `build_matchable_context`-
    equivalent aggregation.
    """
    raise NotImplementedError
