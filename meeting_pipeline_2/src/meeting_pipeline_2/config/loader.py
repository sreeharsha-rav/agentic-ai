"""Config assembly: defaults < JSON file < explicit overrides (e.g. CLI flags).

Port reference: `meeting_pipeline/cli.py::config_from_args()` for the
precedence logic, and `PipelineConfig.from_json`/`.replace()` in
`meeting_pipeline/config.py` for the (de)serialization this builds on.
Kept separate from `schema.py` so schema stays import-light and this module
owns the only place file I/O and CLI-argument interpretation happen for
configuration.
"""

from __future__ import annotations

from pathlib import Path

from .schema import PipelineConfig


def load_from_json(path: str | Path) -> PipelineConfig:
    """Load a `PipelineConfig` from a JSON file.

    TODO: port from `PipelineConfig.from_json` in the original `config.py`.
    """
    raise NotImplementedError


def merge_overrides(base: PipelineConfig, overrides: dict[str, dict]) -> PipelineConfig:
    """Return a copy of `base` with per-section field overrides applied.

    TODO: port from `PipelineConfig.replace()` in the original `config.py`.
    """
    raise NotImplementedError


def resolve_config(config_path: str | Path | None, cli_overrides: dict[str, dict]) -> PipelineConfig:
    """Full precedence chain: built-in defaults < `--config` file < CLI flags.

    TODO: port the composition logic from
    `meeting_pipeline/cli.py::config_from_args()`.
    """
    raise NotImplementedError
