"""Guards pyproject.toml's [project.dependencies] and requirements.txt from
drifting apart -- the exact kind of staleness that made the original
monorepo app's requirements.txt untrustworthy.

Skipped on Python < 3.11, where tomllib isn't in the stdlib.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def _normalize(requirement: str) -> str:
    """Distribution name only, lowercased, underscores/dashes unified."""
    name = re.split(r"[<>=!~;\[]", requirement.strip())[0].strip()
    return name.lower().replace("_", "-")


def _parse_requirements_txt(path: Path) -> set[str]:
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-r"):
            continue
        names.add(_normalize(line))
    return names


def test_pyproject_and_requirements_txt_declare_the_same_core_dependencies():
    tomllib = pytest.importorskip("tomllib")
    pyproject = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pyproject_deps = {_normalize(d) for d in pyproject["project"]["dependencies"]}

    requirements_deps = _parse_requirements_txt(PACKAGE_ROOT / "requirements.txt")

    assert pyproject_deps == requirements_deps
