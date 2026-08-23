"""Shared pytest fixtures.

Port reference: `meeting_pipeline/tests/conftest.py` and
`tests/integration/conftest.py` for the pattern of gating slow tests behind
env vars (`MEETING_PIPELINE_RUN_SLOW`, `MEETING_PIPELINE_TEST_VIDEO`) --
mirror that same gating convention here once integration tests are written,
so both packages' test suites behave consistently in CI.

TODO: add fixtures as real implementations land, e.g.:
  - `tmp_output_dir` -- a pytest `tmp_path`-based `ArtifactPaths` fixture.
  - `sample_vtt_path` -- points at a small fixture VTT under tests/fixtures/.
  - `fake_embedding_provider` -- a `core.interfaces.EmbeddingProvider` test
    double returning deterministic vectors, for testing topic_clustering.py
    and stages/align without loading a real sentence-transformers model.
"""

from __future__ import annotations
