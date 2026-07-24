"""Agentic multivariate-analysis step. MULTI-TURN, v1 scope deliberately limited.

Like the univariate agent, this runs a short conversation with reasoning carried
across turns — but here Turn 1 additionally needs the *actual* correlations to
decide which relationships are worth plotting, so a correlation report is
computed in Python and injected. Turns:

    Turn 1 (SELECTION) — reason over the cleaned-data profile + a precomputed
        correlation report and pick the relationships that clear the threshold
        (or are analytically interesting). No code. `reasoning.context =
        current_turn`.
    Turn 2 (CODE GEN)  — given the selection reasoning (full `output` history is
        replayed), emit ONE matplotlib script that renders exactly those charts.
        `reasoning.context = all_turns`.

The generated script is run in a subprocess; on failure the error is fed back
into the same conversation and the model self-corrects (bounded retries).

Reasoning continuity relies on server-side conversation state: each turn is sent
with `store=True` and the next turn passes the prior response's id as
`previous_response_id`, so the model's reasoning carries across turns without
replaying history manually.

Scope is still numeric-vs-numeric and numeric-vs-categorical plus one overall
correlation heatmap. Categorical-vs-categorical and 3+ variable / time-series
interactions are out of scope for this version — see MULTIVARIATE_*_INSTRUCTIONS
in prompts.py — and should be added as a follow-up rather than folded in here.
"""
from pathlib import Path
from typing import Literal, Optional
from pydantic import BaseModel, Field
from openai import OpenAI

from .prompts import (
    MULTIVARIATE_SELECTION_INSTRUCTIONS,
    MULTIVARIATE_CODEGEN_INSTRUCTIONS,
    MULTIVARIATE_FIX_REQUEST,
)
from agentic_eda.config import OPENAI_API_KEY, MULTIVARIATE_CHARTS_DIR, CORRELATION_THRESHOLD
from agentic_eda.utils import profile_dataset, correlation_profile, execute_chart_generation_code


# ---- OPENAI client ----
client = OpenAI(api_key=OPENAI_API_KEY)
OPENAI_MODEL = "gpt-5.6-terra"


# --------------------------------------------------------------------------- #
# Structured-output schemas — one per turn, plus a combined result for callers.
# --------------------------------------------------------------------------- #

AnalysisPhase = Literal[
    "load",
    "profile",
    "select_relationships",
    "choose_charts",
    "render",
    "save",
    "diagnose_fix",  # used only on a fix-retry turn, per MULTIVARIATE_FIX_REQUEST
]

RelationshipType = Literal[
    "numeric_numeric",
    "numeric_categorical",
    "categorical_categorical_skip",  # out of scope for this v1 stub
    "multiway_skip",                 # out of scope for this v1 stub
]


class ReasoningStep(BaseModel):
    """One phase of the multivariate-analysis chain of thought."""

    phase: AnalysisPhase = Field(
        description="Which stage of the analysis workflow this step covers."
    )
    observation: str = Field(
        description="What the profile / correlation report shows relevant to this phase."
    )
    action: str = Field(
        description="The concrete decision made for this phase."
    )


class RelationshipPlan(BaseModel):
    """How a single pairwise relationship will (or will not) be visualized."""

    variable_x: str = Field(description="First column in the relationship.")
    variable_y: str = Field(
        description="Second column, or '' for the overall correlation heatmap."
    )
    relationship_type: RelationshipType = Field(
        description="Category driving the chart choice; *_skip means out of scope for v1."
    )
    correlation: Optional[float] = Field(
        default=None,
        description=(
            "Observed Pearson r for numeric-vs-numeric pairs (from the injected "
            "correlation report); null for numeric-categorical, the heatmap, and "
            "skipped pairs."
        ),
    )
    meets_threshold: bool = Field(
        description="Whether |correlation| >= the applied threshold (False when not applicable)."
    )
    selected: bool = Field(
        description="Whether this relationship is chosen to be plotted."
    )
    chart_type: str = Field(
        description="Chart chosen, e.g. 'scatter', 'correlation heatmap', 'grouped boxplot', or 'skipped'."
    )
    rationale: str = Field(
        description="Why this chart is selected (or why the pair is skipped)."
    )
    output_filename: str = Field(
        description="PNG filename this relationship writes, or '' when not selected."
    )


class RelationshipSelectionResponse(BaseModel):
    """Turn 1 — which relationships to plot. No code produced in this turn."""

    reasoning_steps: list[ReasoningStep] = Field(
        description="Ordered reasoning for the selection phases (load, profile, select_relationships)."
    )
    correlation_threshold: float = Field(
        description="The |r| threshold applied when selecting numeric-numeric pairs."
    )
    relationship_plans: list[RelationshipPlan] = Field(
        description="A plan for every pair considered, including skipped ones."
    )
    selected_relationships: list[str] = Field(
        description="Human-readable list of the relationships chosen to plot."
    )
    assumptions: list[str] = Field(
        description=(
            "Assumptions made while interpreting the dataset, including any "
            "categorical-categorical or 3+ variable relationship judged "
            "interesting but left out of scope for this v1 stub."
        )
    )


class MultivariateCodeGenResponse(BaseModel):
    """Turn 2 — the matplotlib script rendering the selected relationships."""

    reasoning_steps: list[ReasoningStep] = Field(
        description="Ordered reasoning for the code-gen phases (choose_charts, render, save)."
    )
    summary: str = Field(
        description="One concise sentence describing the multivariate analysis produced."
    )
    code: str = Field(
        description=(
            "Executable Python only; no Markdown fences. Reads the CSV from the "
            "pre-injected `DATASET_PATH` and saves one PNG per selected relationship "
            "(plus one correlation heatmap) into the pre-injected `OUTPUT_DIR`."
        )
    )
    expected_output_files: list[str] = Field(
        description="Exact list of PNG filenames the script will write."
    )


class MultivariateAnalysisResponse(BaseModel):
    """Combined result assembled from both turns, for downstream consumers."""

    reasoning_steps: list[ReasoningStep] = Field(
        description="Selection + code-gen reasoning, in order."
    )
    correlation_threshold: float = Field(
        description="The |r| threshold applied when selecting numeric-numeric pairs."
    )
    relationship_plans: list[RelationshipPlan] = Field(
        description="A plan for every pair considered, including skipped ones."
    )
    summary: str = Field(
        description="One concise sentence describing the multivariate analysis produced."
    )
    code: str = Field(
        description="The final (possibly self-corrected) executable analysis script."
    )
    assumptions: list[str] = Field(
        description="Assumptions and out-of-scope notes from the selection turn."
    )
    expected_output_files: list[str] = Field(
        description="Exact list of PNG filenames the script will write."
    )


# --------------------------------------------------------------------------- #
# The agent: profile -> (turn 1) select -> (turn 2) generate -> execute w/ retry
# Reasoning is carried across turns via server-side state: store=True on each turn
# and previous_response_id chaining, so no manual history replay is needed.
# --------------------------------------------------------------------------- #

def run_multivariate_analysis(
    cleaned_csv_path: str | Path,
    charts_dir: str | Path = MULTIVARIATE_CHARTS_DIR,
    model: str = OPENAI_MODEL,
    threshold: float = CORRELATION_THRESHOLD,
    n_preview: int = 10,
    max_fix_attempts: int = 2,
) -> tuple[MultivariateAnalysisResponse, list[Path]]:
    """
    End-to-end multivariate step.

    Turn 1 selects relationships against a precomputed correlation report; Turn 2
    generates the chart code; the code is executed and, on failure, re-generated
    from the error within the same conversation (up to `max_fix_attempts` times).
    Returns the combined structured response plus the chart PNGs created.
    """
    profile = profile_dataset(cleaned_csv_path, n_preview=n_preview)
    corr_report = correlation_profile(cleaned_csv_path, threshold=threshold)

    # ---- Turn 1: relationship selection ---------------------------------- #
    selection_input = f"""
    Plan the multivariate analysis of the following cleaned dataset. Reason step
    by step over the profile and the precomputed correlation report, then select
    the relationships worth plotting. Apply a correlation threshold of
    |r| >= {threshold} for numeric-numeric pairs (you may justify exceptions).
    Do NOT write plotting code in this turn.

    <dataset_profile>
    {profile}
    </dataset_profile>

    <correlation_report>
    {corr_report}
    </correlation_report>
    """

    selection_response = client.responses.parse(
        model=model,
        store=True,
        instructions=MULTIVARIATE_SELECTION_INSTRUCTIONS,
        input=selection_input,
        reasoning={"context": "current_turn", "effort": "high"},
        text_format=RelationshipSelectionResponse,
    )

    if selection_response.output_parsed is None:
        raise RuntimeError(
            f"Structured turn did not produce a parsed result: {selection_response.output_text}"
        )

    selection_output = selection_response.output_parsed

    # ---- Turn 2: code generation ----------------------------------------- #
    codegen_input = f"""
    Now generate ONE matplotlib script that renders and saves exactly the
    relationships you selected above (including the correlation heatmap). Follow
    the matplotlib compatibility notes.

    Selected Plan:
    <relationship_plans>
    {selection_output.relationship_plans}
    </relationship_plans>
    """

    code_response = client.responses.parse(
        model=model,
        store=True,
        instructions=MULTIVARIATE_CODEGEN_INSTRUCTIONS,
        input=codegen_input,
        previous_response_id=selection_response.id,
        reasoning={"context": "all_turns", "effort": "high"},
        text_format=MultivariateCodeGenResponse,
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
                f"[multivariate] generated code failed "
                f"(attempt {attempt}/{max_fix_attempts}); asking the model to fix it."
            )
            error_fix_input = MULTIVARIATE_FIX_REQUEST.format(error=str(exc))

            code_response = client.responses.parse(
                model=model,
                store=True,
                instructions=MULTIVARIATE_CODEGEN_INSTRUCTIONS,
                input=error_fix_input,
                previous_response_id=code_response.id,
                reasoning={"context": "all_turns", "effort": "medium"},
                text_format=MultivariateCodeGenResponse,
            )

            if code_response.output_parsed is None:
                raise RuntimeError(
                    f"Structured turn did not produce a parsed result: {code_response.output_text}"
                )

            codegen_output = code_response.output_parsed

    combined = MultivariateAnalysisResponse(
        reasoning_steps=[*selection_output.reasoning_steps, *codegen_output.reasoning_steps],
        correlation_threshold=selection_output.correlation_threshold,
        relationship_plans=selection_output.relationship_plans,
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

    result, chart_paths = run_multivariate_analysis(cleaned_csv_path)

    print("=== SUMMARY ===")
    print(result.summary)

    print(f"\n=== CORRELATION THRESHOLD APPLIED ===\n|r| >= {result.correlation_threshold}")

    print("\n=== REASONING STEPS ===")
    for step in result.reasoning_steps:
        print(f"[{step.phase}]")
        print(f"  observation: {step.observation}")
        print(f"  action:      {step.action}")

    print("\n=== RELATIONSHIP PLANS ===")
    for plan in result.relationship_plans:
        pair = f"{plan.variable_x} vs {plan.variable_y}" if plan.variable_y else plan.variable_x
        mark = "[x]" if plan.selected else "[ ]"
        corr = f"r={plan.correlation:+.3f}" if plan.correlation is not None else "r=n/a"
        print(f"  {mark} {pair:<35} {plan.relationship_type:<28} {corr:<12} {plan.chart_type}")
        print(f"      -> {plan.rationale}")

    print("\n=== ASSUMPTIONS / OUT-OF-SCOPE NOTES ===")
    for assumption in result.assumptions:
        print(f"  - {assumption}")

    print("\n=== GENERATED CODE ===")
    print(result.code)

    print("\n=== CHARTS WRITTEN ===")
    for path in chart_paths:
        print(f"  {path}")
