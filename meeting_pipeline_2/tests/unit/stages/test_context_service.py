"""Unit tests for `stages/context/` (topic_clustering / boilerplate_filter / service).

Port reference: `../../../meeting_pipeline/tests/test_topic_grouping.py` and
`test_spatial_layout.py`. `topic_clustering.build_topics()` is directly
testable with plain segment fixtures + a fake `EmbeddingProvider` returning
deterministic vectors -- no real sentence-transformers model needed. Same
for `boilerplate_filter.py` with plain token-set fixtures.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="stages/context/topic_clustering.py not yet implemented")
def test_temporal_gap_forces_new_topic():
    ...


@pytest.mark.skip(reason="stages/context/topic_clustering.py not yet implemented")
def test_semantic_split_requires_min_segments_first():
    ...


@pytest.mark.skip(reason="stages/context/topic_clustering.py not yet implemented")
def test_falls_back_to_time_based_grouping_without_embedding_provider():
    ...


@pytest.mark.skip(reason="stages/context/boilerplate_filter.py not yet implemented")
def test_token_above_document_frequency_threshold_is_stripped():
    ...
