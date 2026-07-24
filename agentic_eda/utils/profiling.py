"""Shared dataset profiling.

A compact text profile (schema, dtypes, nulls, cardinality, preview) is what
grounds every EDA agent in the *real* data instead of guesses. Both the data-
prep agent (raw CSV) and the analysis agents (cleaned CSV) use this.
"""

import io
from pathlib import Path

import pandas as pd


def profile_dataset(dataset_path: str | Path, n_preview: int = 10) -> str:
    """
    Build a compact, text profile of a CSV to hand to an agent.

    Includes schema/dtypes (`df.info()`), per-column null counts, cardinality,
    and a head preview — the same things a human eyeballs before deciding how
    to clean or analyze the data.
    """
    dataset_path = Path(dataset_path)
    frame = pd.read_csv(dataset_path)

    info_buffer = io.StringIO()
    frame.info(buf=info_buffer)

    profile = f"""
File: {dataset_path.name}
Shape: {frame.shape[0]} rows x {frame.shape[1]} columns

--- df.info() ---
{info_buffer.getvalue()}

--- Null counts per column ---
{frame.isnull().sum().to_string()}

--- Distinct values per column ---
{frame.nunique().to_string()}

--- df.head({n_preview}) ---
{frame.head(n_preview).to_string()}
"""
    return profile.strip()


def correlation_profile(dataset_path: str | Path, threshold: float = 0.3) -> str:
    """
    Build a text profile of the numeric correlation structure of a CSV.

    Computes `df.corr(numeric_only=True)` deterministically in Python (no LLM)
    so the multivariate agent selects relationships against *real* numbers, and
    ranks every numeric pair by absolute correlation with an explicit marker for
    those meeting `threshold`. This grounds threshold-based selection instead of
    letting the agent guess which pairs are strongly correlated.
    """
    dataset_path = Path(dataset_path)
    frame = pd.read_csv(dataset_path)
    corr = frame.corr(numeric_only=True)

    columns = list(corr.columns)
    pairs = []
    for i in range(len(columns)):
        for j in range(i + 1, len(columns)):
            r = corr.iloc[i, j]
            pairs.append((columns[i], columns[j], float(r)))
    pairs.sort(key=lambda pair: abs(pair[2]), reverse=True)

    if pairs:
        ranked_lines = "\n".join(
            f"{a} vs {b}: r={r:+.3f}"
            f"{'   >= threshold' if abs(r) >= threshold else ''}"
            for a, b, r in pairs
        )
    else:
        ranked_lines = "(no numeric columns to correlate)"

    profile = f"""
Numeric columns: {columns if columns else '(none)'}
Correlation threshold applied for selection: |r| >= {threshold}

--- df.corr(numeric_only=True) ---
{corr.to_string()}

--- Numeric pairs ranked by |r| (strongest first) ---
{ranked_lines}
"""
    return profile.strip()
