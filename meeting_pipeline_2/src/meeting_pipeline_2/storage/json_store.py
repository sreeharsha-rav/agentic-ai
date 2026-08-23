"""JSON artifact read/write helpers, including best-effort readers for
`pipeline/manifest.py`'s summary-statistics population.

Port reference: the raw `json.load`/`json.dump` calls scattered through
every stage's `save()`/`run()` method in the original, plus the
`_read_segment_count`/`_read_topic_count`/`_read_frame_count`/
`_read_aligned_topic_count` helpers at the bottom of
`meeting_pipeline/pipeline.py`. Centralizing read/write here means a stage's
`service.py` works with typed `core.models` objects, not raw dicts, and
serialization format changes happen in one place.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    """Read and parse a JSON file. TODO: port from the various
    `json.load(open(...))` call sites."""
    raise NotImplementedError


def write_json(path: Path, data: Any, *, indent: int = 2) -> None:
    """Serialize `data` to `path` as JSON, creating parent directories as
    needed. TODO: port from the various `json.dump(...)` call sites."""
    raise NotImplementedError


def read_json_safe(path: Path, default: Any = None) -> Any:
    """Best-effort JSON read: returns `default` on any I/O/parse error
    instead of raising.

    TODO: port the try/except-and-default-to-0 pattern from
    `pipeline.py::_read_segment_count()` et al. -- used for populating
    `PipelineResult` summary stats without letting a malformed/missing
    artifact fail the whole run.
    """
    raise NotImplementedError
