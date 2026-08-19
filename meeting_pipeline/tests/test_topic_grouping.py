from __future__ import annotations

import numpy as np

from meeting_pipeline.config import OCRConfig
from meeting_pipeline.context_builder import MeetingContextBuilder


class _FakeEmbedModel:
    """Returns precomputed vectors regardless of input text -- avoids ever
    loading a real sentence-transformers model in this test."""

    def __init__(self, vectors):
        self._vectors = np.array(vectors, dtype=np.float32)

    def encode(self, texts, **kwargs):
        assert len(texts) == len(self._vectors)
        return self._vectors


def _builder(tmp_path, embeddings_enabled=False):
    return MeetingContextBuilder(
        output_dir=str(tmp_path),
        embeddings_enabled=embeddings_enabled,
        ocr_config=OCRConfig(enabled=False),
    )


def _seg(start, end, speaker="Speaker", transcript="text"):
    return {"start_sec": float(start), "end_sec": float(end), "speaker": speaker, "transcript": transcript}


# -- time-based grouping (no embeddings) -------------------------------------


def test_build_topics_empty_input(tmp_path):
    assert _builder(tmp_path).build_topics([]) == []


def test_build_topics_single_segment(tmp_path):
    topics = _builder(tmp_path).build_topics([_seg(0, 5)])
    assert len(topics) == 1
    assert len(topics[0]) == 1


def test_build_topics_large_gap_splits(tmp_path):
    # gap of 40s > topic_gap_sec default (30.0) forces a split.
    segs = [_seg(0, 5), _seg(45, 50)]
    topics = _builder(tmp_path).build_topics(segs)
    assert len(topics) == 2
    assert [len(t) for t in topics] == [1, 1]


def test_build_topics_contiguous_segments_stay_together(tmp_path):
    segs = [_seg(0, 5), _seg(6, 11), _seg(12, 17)]
    topics = _builder(tmp_path).build_topics(segs)
    assert len(topics) == 1
    assert len(topics[0]) == 3


def test_build_topics_duration_cap_splits(tmp_path):
    # Cumulative duration from the topic's start crosses max_topic_duration_sec
    # (120.0 default) -> forces a split even with zero gaps.
    segs = [_seg(0, 50), _seg(50, 110), _seg(110, 130)]
    topics = _builder(tmp_path).build_topics(segs)
    assert len(topics) == 2
    assert [len(t) for t in topics] == [2, 1]


# -- semantic (embedding-driven) grouping, with a fake embedding model -------


def test_build_topics_semantic_similarity_keeps_segments_merged(tmp_path):
    builder = _builder(tmp_path)
    builder.use_embedding = True
    builder.embed_model = _FakeEmbedModel([[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]])
    segs = [_seg(0, 2), _seg(3, 5), _seg(6, 8)]
    topics = builder.build_topics(segs)
    assert len(topics) == 1
    assert len(topics[0]) == 3


def test_build_topics_semantic_drift_splits_once_two_segments_accumulated(tmp_path):
    builder = _builder(tmp_path)
    builder.use_embedding = True
    # First two segments align (cos=1.0); the third is orthogonal to the
    # running mean (cos=0.0 < 0.68) and len(cur)==2 satisfies the
    # min_segments_before_semantic_split guard -> splits.
    builder.embed_model = _FakeEmbedModel([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    segs = [_seg(0, 2), _seg(3, 5), _seg(6, 8)]
    topics = builder.build_topics(segs)
    assert len(topics) == 2
    assert [len(t) for t in topics] == [2, 1]


def test_build_topics_semantic_drift_does_not_split_with_only_one_segment_accumulated(tmp_path):
    builder = _builder(tmp_path)
    builder.use_embedding = True
    # Only one segment accumulated when the second, orthogonal segment
    # arrives -- len(cur)==1 fails the min_segments_before_semantic_split
    # guard, so no split happens despite cos=0.0 < 0.68.
    builder.embed_model = _FakeEmbedModel([[1.0, 0.0], [0.0, 1.0]])
    segs = [_seg(0, 2), _seg(3, 5)]
    topics = builder.build_topics(segs)
    assert len(topics) == 1
    assert len(topics[0]) == 2
