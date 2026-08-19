"""Top-level orchestration: MeetingPipeline / run_pipeline.

Replaces the old hardcoded, path-specific ``run_meeting_tests.py`` script with
a proper parameterized API. The two module-level boolean toggles that script
used to skip already-completed stages (``SKIP_STEPS_0_TO_3``, ``SKIP_STEP_4``)
are replaced here by per-call ``stages=`` (explicit stage selection) and
``resume=`` (skip a stage if its primary output already exists on disk) --
neither is global state, so multiple pipelines/configs can run concurrently
without interfering with each other.

Stage classes are imported lazily, inside each method, so that constructing a
``MeetingPipeline`` or inspecting a ``PipelineConfig`` never pulls in torch,
opencv, or any other heavy dependency.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Sequence

from .config import PipelineConfig
from .errors import ArtifactNotFoundError

logger = logging.getLogger(__name__)


class Stage(str, Enum):
    """The four pipeline stages, in execution order."""

    TRANSCRIBE = "transcribe"
    FRAMES = "frames"
    CONTEXT = "context"
    ALIGN = "align"


@dataclass
class PipelineResult:
    """Everything a ``MeetingPipeline.run()`` call produced."""

    output_dir: Path
    audio_path: Path | None = None
    transcript_path: Path | None = None
    frames_dir: Path | None = None
    hybrid_log_path: Path | None = None
    timeline_path: Path | None = None
    context_path: Path | None = None
    context_jsonl_path: Path | None = None
    aligned_path: Path | None = None
    aligned_detailed_path: Path | None = None
    segment_count: int = 0
    topic_count: int = 0
    frame_count: int = 0
    aligned_topic_count: int = 0
    stages_run: list[Stage] = field(default_factory=list)
    stages_skipped: list[Stage] = field(default_factory=list)
    stage_seconds: dict[str, float] = field(default_factory=dict)
    config: PipelineConfig = field(default_factory=PipelineConfig)

    def to_dict(self) -> dict:
        def p(x: Path | None) -> str | None:
            return str(x) if x is not None else None

        return {
            "output_dir": p(self.output_dir),
            "audio_path": p(self.audio_path),
            "transcript_path": p(self.transcript_path),
            "frames_dir": p(self.frames_dir),
            "hybrid_log_path": p(self.hybrid_log_path),
            "timeline_path": p(self.timeline_path),
            "context_path": p(self.context_path),
            "context_jsonl_path": p(self.context_jsonl_path),
            "aligned_path": p(self.aligned_path),
            "aligned_detailed_path": p(self.aligned_detailed_path),
            "segment_count": self.segment_count,
            "topic_count": self.topic_count,
            "frame_count": self.frame_count,
            "aligned_topic_count": self.aligned_topic_count,
            "stages_run": [s.value for s in self.stages_run],
            "stages_skipped": [s.value for s in self.stages_skipped],
            "stage_seconds": self.stage_seconds,
            "config": self.config.to_dict(),
        }


class MeetingPipeline:
    """Holds a :class:`PipelineConfig` and runs the 4 stages against it.

    Can be used as a whole (``run``) or one stage at a time (``transcribe``,
    ``extract_frames``, ``build_context``, ``align_documents``) -- each
    individual method mirrors one of the original stage classes 1:1 and
    returns the path to the artifact it produced.
    """

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config or PipelineConfig()

    # -- individual stages ------------------------------------------------

    def transcribe(self, video_path: str | Path, output_dir: str | Path) -> Path:
        from .audio_transcriber import AudioTranscriber

        output_dir = Path(output_dir)
        transcriber = AudioTranscriber.from_config(self.config.transcription)
        return Path(transcriber.run(str(video_path), output_dir=str(output_dir)))

    def extract_frames(
        self, video_path: str | Path, transcript_path: str | Path, output_dir: str | Path
    ) -> Path:
        from .hybrid_extractor import HybridExtractor

        output_dir = Path(output_dir)
        extractor = HybridExtractor.from_config(str(output_dir), self.config.frames)
        extractor.run(str(video_path), str(transcript_path))
        return output_dir / "hybrid_enriched_log.json"

    def build_context(
        self,
        hybrid_log_path: str | Path,
        output_dir: str | Path,
        frames_dir: str | Path | None = None,
    ) -> Path:
        from .context_builder import MeetingContextBuilder

        output_dir = Path(output_dir)
        if frames_dir is None:
            frames_dir = output_dir / "video" / "hybrid"
        builder = MeetingContextBuilder.from_config(
            str(output_dir), self.config.context, self.config.ocr
        )
        _, context_path, _ = builder.run(str(hybrid_log_path), frames_dir=str(frames_dir))
        return Path(context_path)

    def align_documents(
        self,
        context_path: str | Path,
        documents,
        output_dir: str | Path,
    ) -> Path:
        from .document_aligner import DocumentAligner

        output_dir = Path(output_dir)
        aligner = DocumentAligner.from_config(
            str(output_dir), self.config.alignment, self.config.ocr
        )
        aligned_path = aligner.run(str(context_path), documents)
        return Path(aligned_path)

    # -- full pipeline ------------------------------------------------------

    def run(
        self,
        video_path: str | Path,
        output_dir: str | Path,
        documents=None,
        *,
        stages: Sequence[Stage] | None = None,
        resume: bool = False,
        copy_documents: bool = False,
    ) -> PipelineResult:
        """Run some or all of the 4 stages.

        Args:
            video_path: path to the source meeting recording.
            output_dir: directory where all artifacts are written/read.
            documents: reference document path(s) or directory to align
                topics against (passed to ``DocumentAligner``; ``None`` skips
                the ALIGN stage entirely regardless of ``stages``).
            stages: which stages to run, in any subset of ``Stage`` order.
                Defaults to all four. E.g. ``stages=[Stage.CONTEXT, Stage.ALIGN]``
                to re-test only the later stages against already-generated
                Step 0-3 artifacts (the old ``SKIP_STEPS_0_TO_3`` behavior).
            resume: if True, a stage is skipped when its primary output file
                already exists on disk, regardless of ``stages``.
            copy_documents: if True, copy ``documents`` into
                ``output_dir/docs_input/`` before aligning (opt-in -- a
                library should not silently duplicate a caller's files).
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        wanted = set(stages) if stages is not None else set(Stage)

        transcript_path = output_dir / "generated_transcript.vtt"
        audio_path = output_dir / "extracted_audio.wav"
        frames_dir = output_dir / "video" / "hybrid"
        hybrid_log_path = output_dir / "hybrid_enriched_log.json"
        timeline_path = output_dir / "meeting_timeline_clean.json"
        context_path = output_dir / "meeting_context.json"
        context_jsonl_path = output_dir / "meeting_context_for_matching.jsonl"
        aligned_path = output_dir / "aligned_context.json"
        aligned_detailed_path = output_dir / "aligned_context_intermediate_detailed.json"

        stages_run: list[Stage] = []
        stages_skipped: list[Stage] = []
        stage_seconds: dict[str, float] = {}

        def _should_run(stage: Stage, output_exists: bool) -> bool:
            if stage not in wanted:
                stages_skipped.append(stage)
                return False
            if resume and output_exists:
                stages_skipped.append(stage)
                return False
            return True

        if _should_run(Stage.TRANSCRIBE, transcript_path.exists()):
            t0 = time.perf_counter()
            transcript_path = self.transcribe(video_path, output_dir)
            stage_seconds[Stage.TRANSCRIBE.value] = time.perf_counter() - t0
            stages_run.append(Stage.TRANSCRIBE)

        if _should_run(Stage.FRAMES, hybrid_log_path.exists()):
            if not transcript_path.exists():
                raise ArtifactNotFoundError(
                    f"Frame extraction needs a transcript, but none exists at {transcript_path}. "
                    f"Run/include Stage.TRANSCRIBE first."
                )
            t0 = time.perf_counter()
            hybrid_log_path = self.extract_frames(video_path, transcript_path, output_dir)
            stage_seconds[Stage.FRAMES.value] = time.perf_counter() - t0
            stages_run.append(Stage.FRAMES)

        if _should_run(Stage.CONTEXT, context_path.exists()):
            if not hybrid_log_path.exists():
                raise ArtifactNotFoundError(
                    f"Context building needs a hybrid log, but none exists at {hybrid_log_path}. "
                    f"Run/include Stage.FRAMES first."
                )
            t0 = time.perf_counter()
            context_path = self.build_context(hybrid_log_path, output_dir, frames_dir=frames_dir)
            stage_seconds[Stage.CONTEXT.value] = time.perf_counter() - t0
            stages_run.append(Stage.CONTEXT)

        if documents is not None and _should_run(Stage.ALIGN, aligned_path.exists()):
            if not context_path.exists():
                raise ArtifactNotFoundError(
                    f"Document alignment needs a meeting context file, but none exists at "
                    f"{context_path}. Run/include Stage.CONTEXT first."
                )
            docs_for_align = documents
            if copy_documents:
                docs_for_align = self._copy_documents(documents, output_dir)
            t0 = time.perf_counter()
            aligned_path = self.align_documents(context_path, docs_for_align, output_dir)
            stage_seconds[Stage.ALIGN.value] = time.perf_counter() - t0
            stages_run.append(Stage.ALIGN)
        elif documents is None:
            stages_skipped.append(Stage.ALIGN)

        result = PipelineResult(
            output_dir=output_dir,
            audio_path=audio_path if audio_path.exists() else None,
            transcript_path=transcript_path if transcript_path.exists() else None,
            frames_dir=frames_dir if frames_dir.exists() else None,
            hybrid_log_path=hybrid_log_path if hybrid_log_path.exists() else None,
            timeline_path=timeline_path if timeline_path.exists() else None,
            context_path=context_path if context_path.exists() else None,
            context_jsonl_path=context_jsonl_path if context_jsonl_path.exists() else None,
            aligned_path=aligned_path if aligned_path.exists() else None,
            aligned_detailed_path=aligned_detailed_path if aligned_detailed_path.exists() else None,
            segment_count=_read_segment_count(timeline_path),
            topic_count=_read_topic_count(context_path),
            frame_count=_read_frame_count(context_path),
            aligned_topic_count=_read_aligned_topic_count(aligned_path),
            stages_run=stages_run,
            stages_skipped=stages_skipped,
            stage_seconds=stage_seconds,
            config=self.config,
        )
        manifest_path = output_dir / "run_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2)
        return result

    @staticmethod
    def _copy_documents(documents, output_dir: Path) -> Path:
        import shutil

        docs_dir = output_dir / "docs_input"
        docs_dir.mkdir(parents=True, exist_ok=True)
        if isinstance(documents, (str, Path)):
            src = Path(documents)
            paths = sorted(src.iterdir()) if src.is_dir() else [src]
        else:
            paths = [Path(d) for d in documents]
        for doc in paths:
            if not doc.exists():
                logger.warning("Document not found, skipping: %s", doc)
                continue
            shutil.copy2(doc, docs_dir / doc.name)
        return docs_dir


def run_pipeline(
    video_path: str | Path,
    output_dir: str | Path,
    documents=None,
    config: PipelineConfig | None = None,
    **kwargs,
) -> PipelineResult:
    """One-call convenience wrapper around ``MeetingPipeline(config).run(...)``."""
    return MeetingPipeline(config).run(video_path, output_dir, documents, **kwargs)


def _read_segment_count(timeline_path: Path) -> int:
    try:
        with open(timeline_path, encoding="utf-8") as f:
            data = json.load(f)
        return int(data.get("meta", {}).get("total_segments", 0))
    except (OSError, ValueError, AttributeError):
        return 0


def _read_topic_count(context_path: Path) -> int:
    try:
        with open(context_path, encoding="utf-8") as f:
            data = json.load(f)
        return len(data)
    except (OSError, ValueError):
        return 0


def _read_frame_count(context_path: Path) -> int:
    try:
        with open(context_path, encoding="utf-8") as f:
            topics = json.load(f)
        seen = set()
        for topic in topics:
            for frame in topic.get("frames", []):
                seen.add(frame.get("file"))
        return len(seen)
    except (OSError, ValueError, AttributeError):
        return 0


def _read_aligned_topic_count(aligned_path: Path) -> int:
    try:
        with open(aligned_path, encoding="utf-8") as f:
            topics = json.load(f)
        return sum(1 for t in topics if t.get("has_document_alignment"))
    except (OSError, ValueError):
        return 0
