"""Agentic univariate-analysis step. MULTI-TURN.

Consumes the cleaned CSV produced by the data-prep agent. Rather than deciding
what to plot and writing all the code in one shot, this agent runs a short
conversation with reasoning carried across turns:

    Turn 1 (SELECTION) — reason over the cleaned-data profile and decide, per
        column, which single-variable chart to render (or to skip it). No code.
        `reasoning.context = current_turn`.
    Turn 2 (CODE GEN)  — given the per-variable plan (full `output` history is
        replayed), emit ONE matplotlib script that renders exactly those charts.
        `reasoning.context = all_turns`.

The generated script is run in a subprocess; on failure the error is fed back
into the same conversation and the model self-corrects (bounded retries).

Reasoning continuity relies on the shared `conversation.run_structured_turn`
helper (store=False + include=["reasoning.encrypted_content"]); see its docstring.
"""
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field
from openai import OpenAI

from .prompts import (
    UNIVARIATE_SELECTION_INSTRUCTIONS,
    UNIVARIATE_CODEGEN_INSTRUCTIONS,
    UNIVARIATE_FIX_REQUEST,
)
from agentic_eda.config import OPENAI_API_KEY, UNIVARIATE_CHARTS_DIR
from agentic_eda.utils import profile_dataset, execute_chart_generation_code


# ---- OPENAI client ----
client = OpenAI(api_key=OPENAI_API_KEY)
OPENAI_MODEL = "gpt-5.6-luna"


# --------------------------------------------------------------------------- #
# Structured-output schemas — one per turn, plus a combined result for callers.
# --------------------------------------------------------------------------- #

AnalysisPhase = Literal[
    "load",
    "profile",
    "select_variables",
    "choose_charts",
    "render",
    "save",
    "diagnose_fix",  # used only on a fix-retry turn, per UNIVARIATE_FIX_REQUEST
]

DataKind = Literal[
    "numeric_continuous",
    "numeric_discrete",
    "categorical",
    "datetime_part",
    "identifier_skip",
]


class ReasoningStep(BaseModel):
    """One phase of the univariate-analysis chain of thought."""

    phase: AnalysisPhase = Field(
        description="Which stage of the analysis workflow this step covers."
    )
    observation: str = Field(
        description="What the profile shows relevant to this phase."
    )
    action: str = Field(
        description="The concrete decision made for this phase."
    )


class VariablePlan(BaseModel):
    """How a single column will (or will not) be visualized."""

    variable: str = Field(description="Column name being considered.")
    data_kind: DataKind = Field(
        description="Classification driving the chart choice; use 'identifier_skip' to skip."
    )
    chart_type: str = Field(
        description="Chart chosen, e.g. 'histogram', 'boxplot', 'bar counts', or 'skipped'."
    )
    selected: bool = Field(
        description="Whether this variable is chosen to be plotted."
    )
    rationale: str = Field(
        description="Why this chart (or why the column is skipped)."
    )
    output_filename: str = Field(
        description="PNG filename this variable writes, or '' when not selected."
    )


class VariableSelectionResponse(BaseModel):
    """Turn 1 — which variables to plot and how. No code produced in this turn."""

    reasoning_steps: list[ReasoningStep] = Field(
        description="Ordered reasoning for the selection phases (load, profile, select_variables)."
    )
    variable_plans: list[VariablePlan] = Field(
        description="A plan for every column considered, including skipped ones."
    )
    assumptions: list[str] = Field(
        description="Assumptions made while interpreting the dataset."
    )


class UnivariateCodeGenResponse(BaseModel):
    """Turn 2 — the matplotlib script rendering the selected variables."""

    reasoning_steps: list[ReasoningStep] = Field(
        description="Ordered reasoning for the code-gen phases (choose_charts, render, save)."
    )
    summary: str = Field(
        description="One concise sentence describing the univariate analysis produced."
    )
    code: str = Field(
        description=(
            "Executable Python only; no Markdown fences. Reads the CSV from the "
            "pre-injected `DATASET_PATH` and saves one PNG per selected variable "
            "into the pre-injected `OUTPUT_DIR`."
        )
    )
    expected_output_files: list[str] = Field(
        description="Exact list of PNG filenames the script will write."
    )


class UnivariateAnalysisResponse(BaseModel):
    """Combined result assembled from both turns, for downstream consumers."""

    reasoning_steps: list[ReasoningStep] = Field(
        description="Selection + code-gen reasoning, in order."
    )
    variable_plans: list[VariablePlan] = Field(
        description="A plan for every column considered, including skipped ones."
    )
    summary: str = Field(
        description="One concise sentence describing the univariate analysis produced."
    )
    code: str = Field(
        description="The final (possibly self-corrected) executable analysis script."
    )
    assumptions: list[str] = Field(
        description="Assumptions made while interpreting the dataset."
    )
    expected_output_files: list[str] = Field(
        description="Exact list of PNG filenames the script will write."
    )


# --------------------------------------------------------------------------- #
# The agent: profile -> (turn 1) select -> (turn 2) generate -> execute w/ retry
# The shared multi-turn helper (conversation.run_structured_turn) carries the
# reasoning across turns; see its docstring for the store=False / include= detail.
# --------------------------------------------------------------------------- #

def run_univariate_analysis(
    cleaned_csv_path: str | Path,
    charts_dir: str | Path = UNIVARIATE_CHARTS_DIR,
    model: str = OPENAI_MODEL,
    n_preview: int = 10,
    max_fix_attempts: int = 2,
) -> tuple[UnivariateAnalysisResponse, list[Path]]:
    """
    End-to-end univariate step.

    Turn 1 selects a chart per meaningful variable; Turn 2 generates the chart
    code; the code is executed and, on failure, re-generated from the error
    within the same conversation (up to `max_fix_attempts` times). Returns the
    combined structured response plus the chart PNGs created.
    """
    profile = profile_dataset(cleaned_csv_path, n_preview=n_preview)

    # ---- Turn 1: variable selection -------------------------------------- #
    selection_input = f"""
    Plan the univariate analysis of the following cleaned dataset. Reason step
    by step over the profile, then select — per column — which single-variable
    chart to render (or mark the column skipped). Do NOT write plotting code in
    this turn.

    <dataset_profile>
    {profile}
    </dataset_profile>
    """

    selection_response = client.responses.parse(
        model=model,
        store=True,
        instructions=UNIVARIATE_SELECTION_INSTRUCTIONS,
        input=selection_input,
        reasoning={"context": "current_turn", "effort": "medium"},
        text_format=VariableSelectionResponse,
    )

    if selection_response.output_parsed is None:
        raise RuntimeError(
            f"Structured turn did not produce a parsed result: {selection_response.output_text}"
        )

    selection_output = selection_response.output_parsed

    # ---- Turn 2: code generation ----------------------------------------- #
    codegen_input = f"""
    "Now generate ONE matplotlib script that renders and saves exactly "
            "the variables you selected above (one figure each). Follow the "
            "matplotlib compatibility notes."
    Selected Plan:
    <selected_variables>
    {selection_output.variable_plans}
    </selected_variables>
    """

    code_response = client.responses.parse(
        model=model,
        store=True,
        instructions=UNIVARIATE_CODEGEN_INSTRUCTIONS,
        input=codegen_input,
        previous_response_id=selection_response.id,
        reasoning={"context": "all_turns", "effort": "medium"},
        text_format=UnivariateCodeGenResponse,
    )
    
    if code_response.output_parsed is None:
        raise RuntimeError(
            f"Structured turn did not produce a parsed result: {code_response.output_text}"
        )
    
    codegen_output = code_response.output_parsed

    # ---- Execute, self-correcting from errors within the conversation ---- #
    chart_paths: list[Path] = []
    attempt = 0
    while True:
        try:
            chart_paths = execute_chart_generation_code(
                generated_code=codegen_output.code,
                dataset_path=cleaned_csv_path,
                charts_dir=charts_dir,
            )
            break
        except RuntimeError as exc:
            attempt += 1
            if attempt > max_fix_attempts:
                raise
            print(
                f"[univariate] generated code failed "
                f"(attempt {attempt}/{max_fix_attempts}); asking the model to fix it."
            )
            error_fix_input = UNIVARIATE_FIX_REQUEST.format(error=str(exc))

            code_response = client.responses.parse(
                model=model,
                store=True,
                instructions=UNIVARIATE_CODEGEN_INSTRUCTIONS,
                input=error_fix_input,
                previous_response_id=code_response.id,
                reasoning={"context": "all_turns", "effort": "medium"},
                text_format=UnivariateCodeGenResponse,
            )
            
            if code_response.output_parsed is None:
                raise RuntimeError(
                    f"Structured turn did not produce a parsed result: {code_response.output_text}"
                )
            
            codegen_output = code_response.output_parsed

    combined = UnivariateAnalysisResponse(
        reasoning_steps=[*selection_output.reasoning_steps, *codegen_output.reasoning_steps],
        variable_plans=selection_output.variable_plans,
        summary=codegen_output.summary,
        code=codegen_output.code,
        assumptions=selection_output.assumptions,
        expected_output_files=codegen_output.expected_output_files,
    )
    return combined, chart_paths


if __name__ == "__main__":
    import sys
    from agentic_eda.config import CLEANED_DATA_DIR

    # Use a cleaned CSV path from argv, else fall back to the sales default.
    if len(sys.argv) > 1:
        cleaned_csv_path = Path(sys.argv[1])
    else:
        cleaned_csv_path = CLEANED_DATA_DIR / "sales_data_cleaned.csv"

    if not cleaned_csv_path.exists():
        raise SystemExit(
            f"Cleaned CSV not found: {cleaned_csv_path}\n"
            "Run data_prep_agent.py first, or pass a path as an argument."
        )

    result, chart_paths = run_univariate_analysis(cleaned_csv_path)

    print("=== SUMMARY ===")
    print(result.summary)

    print("\n=== REASONING STEPS ===")
    for step in result.reasoning_steps:
        print(f"[{step.phase}]")
        print(f"  observation: {step.observation}")
        print(f"  action:      {step.action}")

    print("\n=== VARIABLE PLANS ===")
    for plan in result.variable_plans:
        mark = "[x]" if plan.selected else "[ ]"
        print(f"  {mark} {plan.variable:<20} {plan.data_kind:<20} {plan.chart_type}")
        print(f"      -> {plan.rationale}")

    print("\n=== ASSUMPTIONS ===")
    for assumption in result.assumptions:
        print(f"  - {assumption}")

    print("\n=== GENERATED CODE ===")
    print(result.code)

    print("\n=== CHARTS WRITTEN ===")
    for path in chart_paths:
        print(f"  {path}")
