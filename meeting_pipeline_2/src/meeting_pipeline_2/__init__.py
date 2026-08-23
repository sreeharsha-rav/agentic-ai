"""meeting_pipeline_2: restructured scaffold for the meeting-processing pipeline.

See ../README.md for the rationale behind this restructuring and
docs/architecture.md for the layer/dependency-direction diagram.

Port reference: `meeting_pipeline/__init__.py` -- same principle applies:
importing this package (or constructing a `Pipeline`/`PipelineConfig`) must
stay cheap. Heavy dependencies (torch, opencv, faster-whisper, OCR backends)
should only be imported inside the stage module that actually needs them,
not at package import time. Once stages exist, mirror the lazy `__getattr__`
pattern from the original `__init__.py` here for the stage service classes.
"""

from __future__ import annotations

__version__ = "0.1.0"

# TODO: once implemented, export the public surface here, e.g.:
#   from .pipeline.orchestrator import Pipeline, PipelineResult, Stage, run_pipeline
#   from .config.schema import PipelineConfig
# Keep stage service classes (Transcriber/FrameExtractor/etc. implementations)
# behind lazy `__getattr__` resolution, as the original package does, so
# `import meeting_pipeline_2` never pulls in torch/opencv/faster-whisper.
