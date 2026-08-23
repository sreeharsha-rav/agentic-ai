"""Command-line interface: ``meeting-pipeline-2`` / ``python -m meeting_pipeline_2``.

Port reference: `meeting_pipeline/cli.py` in full -- `build_parser()`,
`config_from_args()`, and `main()` as separate, independently testable
functions. The one structural difference from the original: this `main()`
is also responsible for constructing the concrete stage instances
(`stages.transcribe.service.WhisperTranscriber`, etc.) and injecting them
into `pipeline.orchestrator.Pipeline` -- this is the one module in the
package allowed to import both `pipeline/` and `stages/` concretely (see
docs/architecture.md).
"""

from __future__ import annotations

import argparse
from typing import Sequence

from .config.loader import resolve_config
from .logging_utils import apply_thread_env, configure_logging
from .pipeline.orchestrator import Pipeline, Stage


def build_parser() -> argparse.ArgumentParser:
    """TODO: port subcommand structure from `cli.py::build_parser()`
    (run/transcribe/frames/context/align, each with its own flags)."""
    raise NotImplementedError


def _build_pipeline(config) -> Pipeline:
    """Construct concrete stage instances and wire them into a `Pipeline`.

    TODO: once each stage's `service.py` exists, import and construct:
        from .stages.transcribe.service import WhisperTranscriber
        from .stages.frames.service import HybridFrameExtractor
        from .stages.context.service import DefaultContextBuilder
        from .stages.align.service import CompositeDocumentAligner
    and pass them to `Pipeline(config, transcriber=..., frame_extractor=...,
    context_builder=..., document_aligner=...)`.
    """
    raise NotImplementedError


def main(argv: Sequence[str] | None = None) -> int:
    """TODO: port from `cli.py::main()`."""
    raise NotImplementedError
