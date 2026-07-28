"""Filesystem layout for uploads and per-run artifacts.

Two jobs:

1. **Per-run isolation.** `utils.executors.execute_chart_generation_code`
   discovers the charts it produced by globbing a directory and filtering on
   mtime. Point two concurrent runs at the same `charts_dir` and each will
   happily claim the other's PNGs. So every run gets its own directory tree and
   the agents are called with explicit `charts_dir=` / `output_csv_path=` /
   `output_path=` arguments. The flat `outputs/{cleaned,charts,reports}`
   directories stay reserved for `pipeline.py` and the notebook.

2. **Path to URL mapping.** Artifacts live on disk but must reach a browser, so
   `outputs/runs/` is served as `/artifacts/` and this module owns the
   translation in both directions.
"""

import re
import secrets
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from agentic_eda.config import RUNS_DIR, UPLOADS_DIR

#: URL prefix that `main.py` mounts `RUNS_DIR` under.
ARTIFACTS_URL_PREFIX = "/artifacts"

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_filename(filename: str) -> str:
    """Reduce an uploaded filename to a safe basename.

    Defends against path traversal (`../`), absolute paths, and Windows drive
    prefixes: only the basename survives and anything outside a conservative
    character set is collapsed to an underscore.
    """
    base = Path(filename.replace("\\", "/")).name
    cleaned = _SAFE_NAME.sub("_", base).strip("._") or "dataset"
    if not cleaned.lower().endswith(".csv"):
        cleaned = f"{cleaned}.csv"
    return cleaned[:120]


def new_id(prefix_time: datetime | None = None) -> str:
    """Sortable, collision-resistant id: `20260728-142530-a1b2c3`."""
    stamp = (prefix_time or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{secrets.token_hex(3)}"


@dataclass(frozen=True)
class RunPaths:
    """The directory tree for a single run."""

    run_id: str
    root: Path

    @property
    def cleaned_dir(self) -> Path:
        return self.root / "cleaned"

    @property
    def univariate_charts_dir(self) -> Path:
        return self.root / "charts" / "univariate"

    @property
    def multivariate_charts_dir(self) -> Path:
        return self.root / "charts" / "multivariate"

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    @property
    def events_path(self) -> Path:
        return self.root / "events.jsonl"

    @property
    def state_path(self) -> Path:
        return self.root / "run.json"

    def cleaned_csv_path(self, dataset_stem: str) -> Path:
        return self.cleaned_dir / f"{dataset_stem}_cleaned.csv"

    def report_path(self, dataset_stem: str) -> Path:
        return self.reports_dir / f"{dataset_stem}_eda_report.md"

    def ensure(self) -> "RunPaths":
        for directory in (
            self.root,
            self.cleaned_dir,
            self.univariate_charts_dir,
            self.multivariate_charts_dir,
            self.reports_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return self


def run_paths(run_id: str) -> RunPaths:
    """Paths for `run_id` (does not create anything)."""
    return RunPaths(run_id=run_id, root=RUNS_DIR / run_id)


def create_run_paths(run_id: str) -> RunPaths:
    """Paths for `run_id`, with the directory tree created."""
    return run_paths(run_id).ensure()


def artifact_url(path: str | Path) -> str | None:
    """Map an on-disk artifact to its public URL, or None if outside RUNS_DIR.

    Returning None rather than raising keeps a stray path from failing a whole
    run — the orchestrator simply omits the artifact.
    """
    try:
        relative = Path(path).resolve().relative_to(RUNS_DIR.resolve())
    except (ValueError, OSError):
        return None
    return f"{ARTIFACTS_URL_PREFIX}/{relative.as_posix()}"


# --------------------------------------------------------------------------- #
# Uploads
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class StoredUpload:
    dataset_id: str
    path: Path
    filename: str
    bytes: int


def upload_dir(dataset_id: str) -> Path:
    return UPLOADS_DIR / dataset_id


def dataset_path(dataset_id: str) -> Path | None:
    """Locate the CSV for `dataset_id`, or None if it is missing."""
    directory = upload_dir(dataset_id)
    if not directory.is_dir():
        return None
    candidates = sorted(directory.glob("*.csv"))
    return candidates[0] if candidates else None


def list_uploads() -> list[StoredUpload]:
    """All stored uploads, newest first (ids are time-prefixed, so name-sortable)."""
    if not UPLOADS_DIR.is_dir():
        return []

    uploads: list[StoredUpload] = []
    for directory in sorted(UPLOADS_DIR.iterdir(), reverse=True):
        if not directory.is_dir():
            continue
        csv_path = dataset_path(directory.name)
        if csv_path is None:
            continue
        uploads.append(
            StoredUpload(
                dataset_id=directory.name,
                path=csv_path,
                filename=csv_path.name,
                bytes=csv_path.stat().st_size,
            )
        )
    return uploads


def open_upload_target(filename: str) -> tuple[str, Path]:
    """Allocate a dataset id and the destination path for a new upload."""
    dataset_id = new_id()
    directory = upload_dir(dataset_id)
    directory.mkdir(parents=True, exist_ok=True)
    return dataset_id, directory / _sanitize_filename(filename)


def discard_upload(dataset_id: str) -> None:
    """Remove a partially written upload (validation failed mid-stream)."""
    shutil.rmtree(upload_dir(dataset_id), ignore_errors=True)


def parse_shape(profile: str) -> tuple[int | None, int | None]:
    """Pull `rows`/`columns` out of a `profile_dataset` string.

    The profile is plain text built for an LLM, so its `Shape: R rows x C columns`
    line is the cheapest way to get the shape without re-reading a 22 MB CSV.
    """
    match = re.search(r"Shape:\s*([\d,]+)\s*rows\s*x\s*([\d,]+)\s*columns", profile)
    if not match:
        return None, None
    try:
        return (
            int(match.group(1).replace(",", "")),
            int(match.group(2).replace(",", "")),
        )
    except ValueError:
        return None, None
