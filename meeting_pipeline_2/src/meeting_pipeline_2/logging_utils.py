"""Logging setup and thread-environment configuration.

Port reference: `meeting_pipeline/logging_utils.py`. Same rule applies here:
this package must never mutate `os.environ` on import -- `apply_thread_env`
is called explicitly by `cli.py` (or any other entry point) before any heavy
dependency (torch, faster-whisper, sentence-transformers) is imported.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("meeting_pipeline_2")
logger.addHandler(logging.NullHandler())


def apply_thread_env(config: object | None = None) -> None:
    """Set thread-pool related environment variables (OMP_NUM_THREADS, etc.)
    to avoid a known CTranslate2/PyTorch deadlock on some platforms.

    TODO: port the env-var logic from
    `meeting_pipeline/logging_utils.py::apply_thread_env()`, driven by
    `config/schema.py`'s runtime config section once it exists.
    """
    raise NotImplementedError


def configure_logging(level: str = "INFO") -> None:
    """Attach a simple stream handler to the package logger at the given level.

    TODO: port from `meeting_pipeline/logging_utils.py::configure_logging()`.
    """
    raise NotImplementedError
