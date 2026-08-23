"""`run_manifest.json` serialization + summary-statistic population.

Port reference: `PipelineResult.to_dict()` and the module-level
`_read_segment_count`/`_read_topic_count`/`_read_frame_count`/
`_read_aligned_topic_count` helpers in `meeting_pipeline/pipeline.py`.
Split out of `orchestrator.py` because "how do we summarize what happened"
is a distinct concern from "what order do stages run in" -- and this module
is the one that actually re-opens written JSON artifacts to compute counts,
which `orchestrator.py` itself doesn't need to know how to do.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .orchestrator import PipelineResult


def summarize(result: PipelineResult, paths: Any) -> dict:
    """Re-read the written artifacts to populate summary counts
    (segment/topic/frame/aligned-topic counts) for the manifest.

    TODO: port from `pipeline.py::_read_segment_count()` et al. -- each
    should degrade to 0 on a missing/malformed file via
    `storage.json_store.read_json_safe()`, never raise.
    """
    raise NotImplementedError


def write_manifest(result: PipelineResult, output_dir: Path) -> Path:
    """Write the full `PipelineResult` (+ summary stats) to
    `output_dir/run_manifest.json`.

    TODO: port from the end of `pipeline.py::MeetingPipeline.run()`.
    """
    raise NotImplementedError
