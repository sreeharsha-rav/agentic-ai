"""Core domain layer: data models + interfaces (ports).

This package is the center of the dependency graph (see docs/architecture.md):
it imports nothing else from meeting_pipeline_2, and every other package may
import from it. Keep it that way -- no I/O, no third-party ML/media
libraries here, only stdlib (dataclasses, typing, abc). That is what makes
`pipeline/orchestrator.py` testable against fake stages: both real stages and
test doubles only need to satisfy the plain-Python protocols defined here.
"""
