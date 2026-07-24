"""Subprocess executors for agent-generated code.

Generated code is never `exec()`-ed in-process. Each executor writes a small
runner script into a temp directory, injects the paths the generated code
expects (`DATASET_PATH`, and either `OUTPUT_CSV_PATH` or `OUTPUT_DIR`), runs it
in a child Python process with a timeout, and validates the artifacts it
produced.
"""

import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _run_runner(runner_source: str, temp_dir: Path, timeout_seconds: int) -> subprocess.CompletedProcess:
    """Write a runner script to `temp_dir` and execute it in a child process."""
    runner_file = temp_dir / "runner.py"
    runner_file.write_text(runner_source, encoding="utf-8")

    try:
        return subprocess.run(
            [sys.executable, str(runner_file)],
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Execution timed out after {timeout_seconds} seconds."
        ) from exc


def execute_data_prep_code(
    *,
    generated_code: str,
    dataset_path: str | Path,
    output_csv_path: str | Path,
    timeout_seconds: int = 120,
) -> Path:
    """
    Run generated data-prep code, then persist the cleaned frame to CSV.

    The generated code:
    - reads the raw CSV from the injected `DATASET_PATH`, and
    - leaves the cleaned result in a DataFrame named `df`.

    This executor appends the persistence step (`df.to_csv(...)`) itself so the
    generated code never writes to disk. Returns the path to the cleaned CSV.
    """
    dataset_path = Path(dataset_path).resolve()
    output_file = Path(output_csv_path).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="eda_prep_") as temp_dir:
        temp_dir = Path(temp_dir)

        runner_source = f'''import sys
from pathlib import Path
import pandas as pd

DATASET_PATH = Path(r"{dataset_path}")
OUTPUT_CSV_PATH = Path(r"{output_file}")

# ---- Generated prep code begins ----
{generated_code}
# ---- Generated prep code ends ----

if "df" not in globals():
    raise RuntimeError("Prep code did not define a DataFrame named 'df'.")

df.to_csv(OUTPUT_CSV_PATH, index=False)
print(f"CLEANED_ROWS={{len(df)}}")
print(f"CLEANED_COLUMNS={{list(df.columns)}}")
'''

        result = _run_runner(runner_source, temp_dir, timeout_seconds)

        if result.returncode != 0:
            raise RuntimeError(
                "Generated data-prep code failed.\n\n"
                f"STDOUT:\n{result.stdout}\n\n"
                f"STDERR:\n{result.stderr}"
            )

    if not output_file.exists() or output_file.stat().st_size == 0:
        raise RuntimeError(
            f"Execution finished but produced no cleaned CSV at: {output_file}"
        )

    return output_file


def execute_chart_generation_code(
    *,
    generated_code: str,
    dataset_path: str | Path,
    charts_dir: str | Path,
    timeout_seconds: int = 180,
) -> list[Path]:
    """
    Run generated chart-analysis code that saves one PNG per chart.

    Shared by any analysis agent (univariate, multivariate, ...) whose
    generated code reads a CSV from the injected `DATASET_PATH` and writes
    charts into the injected `OUTPUT_DIR`. Returns the list of PNG files
    created (or refreshed) during this run.
    """
    dataset_path = Path(dataset_path).resolve()
    charts_dir = Path(charts_dir).resolve()
    charts_dir.mkdir(parents=True, exist_ok=True)

    started_at = time.time()

    with tempfile.TemporaryDirectory(prefix="eda_chart_") as temp_dir:
        temp_dir = Path(temp_dir)

        runner_source = f'''import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")  # headless backend for a subprocess
import pandas as pd

DATASET_PATH = Path(r"{dataset_path}")
OUTPUT_DIR = Path(r"{charts_dir}")

# ---- Generated analysis code begins ----
{generated_code}
# ---- Generated analysis code ends ----
'''

        result = _run_runner(runner_source, temp_dir, timeout_seconds)

        if result.returncode != 0:
            raise RuntimeError(
                "Generated chart-analysis code failed.\n\n"
                f"STDOUT:\n{result.stdout}\n\n"
                f"STDERR:\n{result.stderr}"
            )

    created = sorted(
        path
        for path in charts_dir.glob("*.png")
        if path.stat().st_mtime >= started_at and path.stat().st_size > 0
    )

    if not created:
        raise RuntimeError(
            f"Execution finished but produced no chart PNGs in: {charts_dir}"
        )

    return created
