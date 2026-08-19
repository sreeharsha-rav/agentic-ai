"""Full pipeline run against a real meeting video. Gated behind an env var
(not just a marker) so it can never fire accidentally in CI -- no video
fixture is committed to this repo.
"""

from __future__ import annotations

import os
import shutil

import pytest

from meeting_pipeline import PipelineConfig, run_pipeline
from meeting_pipeline.pipeline import Stage

pytestmark = [pytest.mark.slow, pytest.mark.integration]

TEST_VIDEO = os.environ.get("MEETING_PIPELINE_TEST_VIDEO")


def _ocr_backend_available() -> bool:
    for mod_name in ("rapidocr_onnxruntime", "paddleocr", "easyocr", "pytesseract"):
        try:
            __import__(mod_name)
            return True
        except ImportError:
            continue
    return False


requires_full_env = pytest.mark.skipif(
    not TEST_VIDEO or not os.path.exists(TEST_VIDEO) or shutil.which("ffmpeg") is None or not _ocr_backend_available(),
    reason=(
        "set MEETING_PIPELINE_TEST_VIDEO to a real video path, with ffmpeg "
        "and at least one OCR backend installed"
    ),
)


@requires_full_env
def test_full_pipeline_against_real_video(tmp_path, fixtures_dir):
    docs = [str(fixtures_dir / "docs" / "sample_reference.md")]

    result = run_pipeline(TEST_VIDEO, str(tmp_path), documents=docs)

    assert result.transcript_path is not None and result.transcript_path.exists()
    assert result.hybrid_log_path is not None and result.hybrid_log_path.exists()
    assert result.context_path is not None and result.context_path.exists()
    assert result.aligned_path is not None and result.aligned_path.exists()
    assert result.topic_count > 0
    assert set(result.stages_run) == set(Stage)

    manifest_path = tmp_path / "run_manifest.json"
    assert manifest_path.exists()

    restored_config = PipelineConfig.from_dict(result.to_dict()["config"])
    assert restored_config == result.config
