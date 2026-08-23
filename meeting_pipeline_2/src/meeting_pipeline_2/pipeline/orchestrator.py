"""`Pipeline`: runs the four stages against a `PipelineConfig`, via their
`core.interfaces` protocols only.

Port reference: `meeting_pipeline/pipeline.py::MeetingPipeline` in full --
the `Stage` enum, the `_should_run()` resume/stage-selection gate, the
per-stage artifact-existence validation (raising `ArtifactNotFoundError`),
and the `stages=`/`resume=`/`copy_documents=` semantics on `run()`. The
algorithm is unchanged; what's different is that this version is constructed
with **injected stage instances** (satisfying `Transcriber`/`FrameExtractor`/
`ContextBuilder`/`DocumentAligner`) rather than lazily importing concrete
classes inline -- see `docs/architecture.md`'s dependency diagram for why.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Sequence

from ..config.schema import PipelineConfig
from ..core.interfaces import ContextBuilder, DocumentAligner, FrameExtractor, Transcriber


class Stage(str, Enum):
    """The four pipeline stages, in execution order.

    TODO: port from `pipeline.py::Stage`.
    """

    TRANSCRIBE = "transcribe"
    FRAMES = "frames"
    CONTEXT = "context"
    ALIGN = "align"


@dataclass
class PipelineResult:
    """Everything one `Pipeline.run()` call produced.

    TODO: port fields + `to_dict()` from `pipeline.py::PipelineResult`.
    """

    output_dir: Path
    stages_run: list[Stage] = field(default_factory=list)
    stages_skipped: list[Stage] = field(default_factory=list)
    stage_seconds: dict[str, float] = field(default_factory=dict)


class Pipeline:
    """Orchestrates the 4 stages via their `core.interfaces` protocols.

    Constructed with concrete stage implementations injected -- this class
    never imports from `stages/` directly, so it can be unit-tested with
    fakes satisfying `Transcriber`/`FrameExtractor`/`ContextBuilder`/
    `DocumentAligner` and no real model/video/ffmpeg dependency.
    """

    def __init__(
        self,
        config: PipelineConfig,
        *,
        transcriber: Transcriber,
        frame_extractor: FrameExtractor,
        context_builder: ContextBuilder,
        document_aligner: DocumentAligner,
    ) -> None:
        self.config = config
        self._transcriber = transcriber
        self._frame_extractor = frame_extractor
        self._context_builder = context_builder
        self._document_aligner = document_aligner

    def run(
        self,
        video_path: str | Path,
        output_dir: str | Path,
        documents: Sequence[str | Path] | None = None,
        *,
        stages: Sequence[Stage] | None = None,
        resume: bool = False,
        copy_documents: bool = False,
    ) -> PipelineResult:
        """Run some or all of the 4 stages.

        TODO: port the full algorithm from `pipeline.py::MeetingPipeline.run()`:
          1. Resolve artifact paths via `storage.artifact_paths.resolve_artifact_paths()`.
          2. Resolve `wanted` stages (default: all four).
          3. For each stage in order: check `stages`-membership, then
             `resume`-and-output-exists, then required-input-exists (raise
             `ArtifactNotFoundError` if missing), then invoke the stage
             through its `core.interfaces` protocol method and time it.
          4. ALIGN is skipped entirely if `documents is None`, regardless of
             `stages`.
          5. Assemble + return a `PipelineResult`, and write it as
             `run_manifest.json` via `storage.json_store.write_json()`.
        """
        raise NotImplementedError
