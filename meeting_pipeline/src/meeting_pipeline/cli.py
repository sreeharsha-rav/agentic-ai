"""Command-line interface: ``meeting-pipeline`` / ``python -m meeting_pipeline``.

``build_parser()`` and ``config_from_args()`` are plain functions, separate
from ``main()``, so the CLI's argument handling is testable without ever
running a pipeline stage.
"""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from .config import PipelineConfig
from .logging_utils import apply_thread_env, configure_logging
from .pipeline import MeetingPipeline, Stage

_OCR_BACKEND_CHOICES = ("rapid", "paddle", "easy", "tesseract", "none")
_SPATIAL_MODE_CHOICES = ("spatial_hierarchical", "flat")


def _add_transcription_args(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--whisper-model", dest="whisper_model", default=None, help="e.g. base.en, small.en, medium.en")
    sub.add_argument("--device", default=None, choices=["cpu", "cuda"])
    sub.add_argument("--language", default=None, help="Spoken language code, e.g. en")


def _add_ocr_args(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--ocr-backend", dest="ocr_backend", default=None, choices=_OCR_BACKEND_CHOICES)
    sub.add_argument("--no-ocr", dest="no_ocr", action="store_true", help="Disable OCR entirely (transcript-only)")
    sub.add_argument("--spatial-mode", dest="spatial_mode", default=None, choices=_SPATIAL_MODE_CHOICES)


def _add_context_args(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--no-embedding", dest="no_embedding", action="store_true", help="Disable semantic topic clustering")


def _add_docs_args(sub: argparse.ArgumentParser, required: bool = False) -> None:
    group = sub.add_mutually_exclusive_group(required=required)
    group.add_argument("--docs", nargs="+", default=None, help="One or more reference document paths")
    group.add_argument("--docs-dir", default=None, help="Directory of reference documents")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meeting-pipeline", description="Temporal multimodal meeting processing pipeline"
    )
    parser.add_argument("--config", default=None, help="Path to a JSON PipelineConfig file")
    parser.add_argument("--print-config", action="store_true", help="Print the resolved config as JSON and exit")
    parser.add_argument("--log-level", default="INFO")

    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="Run some or all pipeline stages end-to-end")
    p_run.add_argument("--video", required=True)
    p_run.add_argument("--out", required=True, dest="output_dir")
    _add_docs_args(p_run)
    p_run.add_argument("--stages", default=None, help="Comma-separated subset of: transcribe,frames,context,align")
    p_run.add_argument("--resume", action="store_true", help="Skip a stage if its output already exists")
    p_run.add_argument("--copy-documents", action="store_true")
    _add_transcription_args(p_run)
    _add_ocr_args(p_run)
    _add_context_args(p_run)

    p_transcribe = sub.add_parser("transcribe", help="Run Step 0 (transcription) only")
    p_transcribe.add_argument("--video", required=True)
    p_transcribe.add_argument("--out", required=True, dest="output_dir")
    _add_transcription_args(p_transcribe)

    p_frames = sub.add_parser("frames", help="Run Steps 1-3 (frame extraction) only")
    p_frames.add_argument("--video", required=True)
    p_frames.add_argument("--vtt", required=True, dest="transcript_path")
    p_frames.add_argument("--out", required=True, dest="output_dir")

    p_context = sub.add_parser("context", help="Run Step 4 (context building) only")
    p_context.add_argument("--log", required=True, dest="hybrid_log_path")
    p_context.add_argument("--frames", default=None, dest="frames_dir")
    p_context.add_argument("--out", required=True, dest="output_dir")
    _add_ocr_args(p_context)
    _add_context_args(p_context)

    p_align = sub.add_parser("align", help="Run Step 5 (document alignment) only")
    p_align.add_argument("--context", required=True, dest="context_path")
    _add_docs_args(p_align, required=True)
    p_align.add_argument("--out", required=True, dest="output_dir")
    _add_ocr_args(p_align)

    return parser


def config_from_args(args: argparse.Namespace) -> PipelineConfig:
    """Build a PipelineConfig from parsed CLI args.

    Precedence: built-in defaults < ``--config`` JSON file < explicit
    per-flag overrides (e.g. ``--ocr-backend``).
    """
    config = PipelineConfig.from_json(args.config) if getattr(args, "config", None) else PipelineConfig()

    overrides: dict[str, dict] = {}

    def _set(section: str, key: str, value) -> None:
        overrides.setdefault(section, {})[key] = value

    if getattr(args, "whisper_model", None):
        _set("transcription", "model_size", args.whisper_model)
    if getattr(args, "device", None):
        _set("transcription", "device", args.device)
    if getattr(args, "language", None):
        _set("transcription", "language", args.language)
    if getattr(args, "ocr_backend", None):
        _set("ocr", "backend", args.ocr_backend)
    if getattr(args, "no_ocr", False):
        _set("ocr", "enabled", False)
    if getattr(args, "spatial_mode", None):
        _set("ocr", "spatial_mode", args.spatial_mode)
    if getattr(args, "no_embedding", False):
        _set("context", "embeddings_enabled", False)

    return config.replace(**overrides) if overrides else config


def _parse_stages(value: str | None) -> list[Stage] | None:
    if not value:
        return None
    return [Stage(v.strip()) for v in value.split(",") if v.strip()]


def _resolve_documents(args: argparse.Namespace):
    docs = getattr(args, "docs", None)
    docs_dir = getattr(args, "docs_dir", None)
    return docs if docs else docs_dir


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = config_from_args(args)

    if args.print_config:
        print(json.dumps(config.to_dict(), indent=2))
        return 0

    if not args.command:
        parser.error("a command is required (run/transcribe/frames/context/align), or pass --print-config")
        return 2

    apply_thread_env(config.runtime)
    configure_logging(args.log_level)

    pipeline = MeetingPipeline(config)

    if args.command == "run":
        try:
            stages = _parse_stages(args.stages)
        except ValueError as exc:
            parser.error(f"invalid --stages value: {exc}")
            return 2
        result = pipeline.run(
            args.video,
            args.output_dir,
            documents=_resolve_documents(args),
            stages=stages,
            resume=args.resume,
            copy_documents=args.copy_documents,
        )
        print(json.dumps(result.to_dict(), indent=2))
    elif args.command == "transcribe":
        print(str(pipeline.transcribe(args.video, args.output_dir)))
    elif args.command == "frames":
        print(str(pipeline.extract_frames(args.video, args.transcript_path, args.output_dir)))
    elif args.command == "context":
        print(str(pipeline.build_context(args.hybrid_log_path, args.output_dir, frames_dir=args.frames_dir)))
    elif args.command == "align":
        print(str(pipeline.align_documents(args.context_path, _resolve_documents(args), args.output_dir)))
    else:
        parser.error(f"Unknown command: {args.command}")
        return 2

    return 0
