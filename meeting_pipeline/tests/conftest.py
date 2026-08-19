"""Shared pytest fixtures.

The autouse fixture below forces the HuggingFace/transformers offline env
vars for every test NOT marked ``slow``. That turns any accidental network
call (e.g. someone instantiating ``SentenceTransformer`` in a non-slow test)
into a loud, immediate failure instead of a silent multi-second model
download -- which is exactly the mistake the tiered test strategy in
docs/architecture.md and the project README is designed to prevent.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _offline_unless_slow(request: pytest.FixtureRequest) -> None:
    if "slow" in request.keywords:
        yield
        return

    old_values = {
        k: os.environ.get(k) for k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
    }
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        yield
    finally:
        for k, v in old_values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR
