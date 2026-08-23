"""Orchestration layer: runs stages in order, resolves stage-subset/resume
logic, writes the run manifest.

Depends only on `core.interfaces` to invoke stages -- never imports a
concrete stage class from `stages/`. The concrete stage instances are handed
in by whatever constructs the `Pipeline` (typically `cli.py`), which is the
one place allowed to know about both `pipeline/` and `stages/` at once. This
is what keeps orchestration testable with fake stages (see docs/architecture.md).
"""
