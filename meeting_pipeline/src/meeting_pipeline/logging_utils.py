"""Logging setup and thread-environment configuration.

A library must never mutate ``os.environ`` on import. ``apply_thread_env`` is
provided so an application (or the CLI) can opt into the thread-pool settings
that avoid a known CTranslate2/PyTorch deadlock on some platforms, at a time
of its own choosing -- before any heavy dependency (torch, faster-whisper,
sentence-transformers) has been imported.
"""

from __future__ import annotations

import logging
import os

from .config import RuntimeConfig

logger = logging.getLogger("meeting_pipeline")
logger.addHandler(logging.NullHandler())


def apply_thread_env(config: RuntimeConfig | None = None) -> None:
    """Set thread-pool related environment variables.

    Must be called before importing torch/faster-whisper/sentence-transformers
    for the settings to take effect. Safe to call multiple times.
    """
    config = config or RuntimeConfig()
    if config.omp_num_threads is not None:
        os.environ["OMP_NUM_THREADS"] = str(config.omp_num_threads)
    os.environ["TOKENIZERS_PARALLELISM"] = "true" if config.tokenizers_parallelism else "false"
    if config.kmp_duplicate_lib_ok:
        os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"


def configure_logging(level: str = "INFO") -> None:
    """Attach a simple stream handler to the package logger at the given level.

    Intended for CLI/script entry points. Library callers should configure
    logging themselves; meeting_pipeline never calls this on import.
    """
    logger.setLevel(level.upper())
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s"))
        logger.addHandler(handler)
