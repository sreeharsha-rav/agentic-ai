"""Agentic data-preparation step.

An LLM is shown a real profile of the raw dataset, reasons — as structured
`reasoning_steps` — about how to clean it, and emits an executable pandas
script that loads, validates, normalizes (date -> Year/Month/Day/Hour is
mandatory) and trims the DataFrame. The script is then run in a subprocess and
the cleaned frame is persisted to CSV for downstream agents.
"""

from pathlib import Path
from typing import Any, Callable, Literal, Optional
from pydantic import BaseModel, Field
from openai import OpenAI

from agentic_eda.config import OPENAI_API_KEY, DATA_DIR, CLEANED_DATA_DIR
from .prompts import DATA_PREP_INSTRUCTIONS
from agentic_eda.utils import profile_dataset, execute_data_prep_code

# Optional progress sink: `on_event(name, payload)`. Defaults to a no-op so the
# CLI and notebook paths behave exactly as before; the web server passes a hook
# that forwards each event to its SSE stream.
ProgressHook = Optional[Callable[[str, dict[str, Any]], None]]


# ---- OPENAI client ----
client = OpenAI(api_key=OPENAI_API_KEY)
OPENAI_MODEL = "gpt-5.6-luna"

# --------------------------------------------------------------------------- #
# Structured-output schema (reasoning steps + generated code)
# --------------------------------------------------------------------------- #

WorkflowPhase = Literal[
    "load",
    "inspect",
    "preview",
    "null_check",
    "type_validation",
    "date_normalization",
    "column_cleanup",
]

ColumnRole = Literal["kept", "derived", "dropped"]


class ReasoningStep(BaseModel):
    """One phase of the data-prep chain of thought."""

    phase: WorkflowPhase = Field(
        description="Which stage of the data-prep workflow this step covers."
    )
    observation: str = Field(
        description="What the profile shows about the data for this phase."
    )
    action: str = Field(
        description="The concrete check or transformation decided for this phase."
    )


class ColumnSpec(BaseModel):
    """A column in the final, cleaned DataFrame."""

    name: str = Field(description="Column name in the cleaned DataFrame.")
    dtype: str = Field(description="Expected pandas dtype, e.g. 'int64', 'float64', 'object'.")
    role: ColumnRole = Field(
        description="'kept' (unchanged), 'derived' (computed here), or 'dropped'."
    )


class DataPrepResponse(BaseModel):
    """Validated response returned by the data-prep generation call."""

    reasoning_steps: list[ReasoningStep] = Field(
        description="Ordered reasoning, one entry per workflow phase."
    )
    detected_date_column: str = Field(
        description="Source column parsed into a datetime for normalization."
    )
    derived_columns: list[str] = Field(
        description="Columns computed during prep; must include Year, Month, Day, Hour."
    )
    dropped_columns: list[str] = Field(
        description="Columns removed as redundant after normalization."
    )
    final_columns: list[ColumnSpec] = Field(
        description="Ordered schema of the cleaned DataFrame the script produces."
    )
    summary: str = Field(
        description="One concise sentence describing the cleaning performed."
    )
    code: str = Field(
        description=(
            "Executable Python only; no Markdown fences or explanation. Loads the "
            "CSV from the pre-injected `DATASET_PATH`, validates/normalizes it, and "
            "leaves the cleaned frame in a DataFrame named `df`."
        )
    )
    assumptions: list[str] = Field(
        description="Assumptions made while interpreting the dataset."
    )


# --------------------------------------------------------------------------- #
# The agent: profile -> reason -> generate prep code
# --------------------------------------------------------------------------- #

def generate_data_prep_code(
    dataset_path: str | Path,
    model: str = OPENAI_MODEL,
    n_preview: int = 10,
    on_event: ProgressHook = None,
) -> DataPrepResponse:
    """
    Profile the raw dataset, then have the LLM reason about it and produce an
    executable pandas prep script (validated via Structured Outputs).

    The generated code assumes `DATASET_PATH` is pre-injected at execution time.
    `on_event` optionally receives progress events; see `ProgressHook`.
    """
    dataset_path = Path(dataset_path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Data file does not exist at path: {dataset_path}")

    emit = on_event or (lambda name, payload: None)

    emit("progress", {"message": f"profiling raw dataset ({dataset_path.name})"})
    profile = profile_dataset(dataset_path, n_preview=n_preview)

    if on_event is None:
        # Preserve the original CLI/notebook behaviour of dumping the profile.
        print(f"============================================")
        print(profile)
        print(f"============================================")
    else:
        emit("profile", {"kind": "dataset", "text": profile})

    input_text = f"""
    Prepare the following dataset for analysis. Reason step by step over the
    profile, then generate the prep code.

    <dataset_profile>
    {profile}
    </dataset_profile>
    """

    emit("progress", {"message": "reasoning over the profile and generating prep code"})
    response = client.responses.parse(
        model=model,
        reasoning={
            "context": "current_turn",
            "effort": "medium"
        },
        instructions=DATA_PREP_INSTRUCTIONS,
        input=input_text,
        text_format=DataPrepResponse,
    )

    if response.output_parsed is None:
        raise RuntimeError(
            f"Data-prep generation did not produce a parsed result: "
            f"{response.output_text}"
        )

    parsed = response.output_parsed

    emit("turn_completed", {
        "turn": "prep",
        "data": parsed.model_dump(mode="json", exclude={"code"}),
    })
    for index, step in enumerate(parsed.reasoning_steps):
        emit("reasoning", {"index": index, **step.model_dump(mode="json")})
    emit("code", {"language": "python", "code": parsed.code})

    return parsed


def run_data_prep(
    dataset_path: str | Path,
    output_csv_path: str | Path | None = None,
    model: str = OPENAI_MODEL,
    on_event: ProgressHook = None,
) -> tuple[DataPrepResponse, Path]:
    """
    End-to-end prep step: generate the code, execute it, and persist the
    cleaned CSV. Returns the structured response and the cleaned-CSV path.

    `on_event` optionally receives progress events; see `ProgressHook`.
    """
    dataset_path = Path(dataset_path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Data file does not exist at path: {dataset_path}")

    if output_csv_path is None:
        output_csv_path = CLEANED_DATA_DIR / f"{dataset_path.stem}_cleaned.csv"

    emit = on_event or (lambda name, payload: None)

    result = generate_data_prep_code(dataset_path, model=model, on_event=on_event)

    emit("progress", {"message": "executing generated cleaning code in a subprocess"})
    cleaned_path = execute_data_prep_code(
        generated_code=result.code,
        dataset_path=dataset_path,
        output_csv_path=output_csv_path,
    )

    emit("artifact", {"kind": "cleaned_csv", "path": str(cleaned_path)})
    emit("summary", {"summary": result.summary})

    return result, cleaned_path


if __name__ == "__main__":
    dataset_path = DATA_DIR / "sales_data.csv"

    result, cleaned_path = run_data_prep(dataset_path)

    print("=== SUMMARY ===")
    print(result.summary)

    print("\n=== REASONING STEPS ===")
    for step in result.reasoning_steps:
        print(f"[{step.phase}]")
        print(f"  observation: {step.observation}")
        print(f"  action:      {step.action}")

    print("\n=== DETECTED DATE COLUMN ===")
    print(result.detected_date_column)

    print("\n=== DERIVED COLUMNS ===")
    print(result.derived_columns)

    print("\n=== DROPPED COLUMNS ===")
    print(result.dropped_columns)

    print("\n=== FINAL SCHEMA ===")
    for col in result.final_columns:
        print(f"  {col.name:<20} {col.dtype:<10} ({col.role})")

    print("\n=== GENERATED CODE ===")
    print(result.code)

    print(f"\n=== CLEANED CSV WRITTEN TO ===\n{cleaned_path}")
