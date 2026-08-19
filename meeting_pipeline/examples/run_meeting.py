#!/usr/bin/env python
"""Example: run the full pipeline against a real meeting recording.

Parameterized replacement for the original internal driver script (which
hardcoded one contributor's file paths). All paths here come from the
command line -- nothing is hardcoded.

Usage:
    python examples/run_meeting.py \\
        --video /path/to/meeting.mp4 \\
        --out ./output/my_meeting \\
        --docs spec.md slides.pptx design.pdf

    # Re-test only document alignment against already-generated context:
    python examples/run_meeting.py \\
        --video /path/to/meeting.mp4 \\
        --out ./output/my_meeting \\
        --docs spec.md \\
        --stages align --resume
"""

from __future__ import annotations

import argparse
import json
import sys

from meeting_pipeline import MeetingPipeline, PipelineConfig, Stage
from meeting_pipeline.logging_utils import apply_thread_env, configure_logging


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

    config = PipelineConfig.from_json(args.config) if args.config else PipelineConfig()
    apply_thread_env(config.runtime)
    configure_logging(args.log_level)

    stages = [Stage(s.strip()) for s in args.stages.split(",")] if args.stages else None

    pipeline = MeetingPipeline(config)
    result = pipeline.run(
        args.video,
        args.output_dir,
        documents=args.docs,
        stages=stages,
        resume=args.resume,
    )

    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
