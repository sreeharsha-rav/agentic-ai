#!/usr/bin/env python
"""Example: run the full pipeline against a real meeting recording.

Port reference: `../../meeting_pipeline/examples/run_meeting.py`. The only
structural difference once implemented: `main()` here builds concrete stage
instances and injects them into `pipeline.orchestrator.Pipeline` (see
`cli.py::_build_pipeline` for the same wiring) rather than the
orchestrator lazily importing stage classes itself.
"""

from __future__ import annotations

import argparse
import json
import sys


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--video", required=True, help="Path to the meeting recording (mp4)")
    parser.add_argument("--out", required=True, dest="output_dir", help="Directory for all pipeline artifacts")
    parser.add_argument("--docs", nargs="*", default=None, help="Reference document paths to align against")
    parser.add_argument(
        "--stages",
        default=None,
        help="Comma-separated subset of transcribe,frames,context,align (default: all)",
    )
    parser.add_argument("--resume", action="store_true", help="Skip a stage if its output already exists")
    parser.add_argument("--config", default=None, help="Path to a JSON PipelineConfig file")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    # TODO once implemented:
    #   from meeting_pipeline_2.config.loader import resolve_config
    #   from meeting_pipeline_2.logging_utils import apply_thread_env, configure_logging
    #   from meeting_pipeline_2.pipeline.orchestrator import Stage
    #   from meeting_pipeline_2.cli import _build_pipeline  # or duplicate its wiring here
    #
    #   config = resolve_config(args.config, {})
    #   apply_thread_env(config.runtime)
    #   configure_logging(args.log_level)
    #   stages = [Stage(s.strip()) for s in args.stages.split(",")] if args.stages else None
    #   pipeline = _build_pipeline(config)
    #   result = pipeline.run(args.video, args.output_dir, documents=args.docs,
    #                          stages=stages, resume=args.resume)
    #   print(json.dumps(result.to_dict(), indent=2))
    raise NotImplementedError("wire this up once pipeline/orchestrator.py and stages/ are implemented")


if __name__ == "__main__":
    sys.exit(main())
