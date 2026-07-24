"""Agentic report step — synthesize the pipeline's context into a markdown report.

Design intent:
- The CONTEXT container (`EdaContext`) and its aggregation are CONCRETE, so the
  interface every upstream stage feeds into is real and stable.
- The report NARRATIVE is produced by a single, MULTIMODAL LLM call: the aggregated
  per-stage context (profile, correlation report, plans, reasoning, summaries) is
  serialized to text and the chart PNGs are attached as images, so the model reasons
  over what the charts actually show — not just their filenames. It returns a
  structured `EdaReportResponse` (per-section prose + per-chart findings).
- The report ASSEMBLY stays CONCRETE and deterministic: it walks a fixed, ordered
  list of section renderers that drop the model's prose into place, pair each chart
  image with its finding (via report-relative links), embed the generated code in an
  appendix, and write valid markdown to disk. Python owns layout and image paths so
  the model never has to guess them.

Like the other agents in this package, this module defines its own OpenAI `client`
and `OPENAI_MODEL` locally. Because the report reads chart images, `OPENAI_MODEL`
must be a model that supports both vision and Structured Outputs / `responses.parse`.
"""

import base64
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Literal, Optional

from pydantic import BaseModel, Field
from openai import OpenAI

from .prompts import REPORT_INSTRUCTIONS
from agentic_eda.config import OPENAI_API_KEY, REPORTS_DIR
from agentic_eda.utils import profile_dataset, correlation_profile

if TYPE_CHECKING:  # keep the report module importable without pulling the agents in
    from agentic_eda.data_prep.agent import DataPrepResponse
    from agentic_eda.univariate_analysis.agent import UnivariateAnalysisResponse
    from agentic_eda.multivariate_analysis.agent import MultivariateAnalysisResponse


# ---- OPENAI client ----
client = OpenAI(api_key=OPENAI_API_KEY)
# Must support vision + Structured Outputs (this is a multimodal synthesis call).
OPENAI_MODEL = "gpt-5.6-terra"


# --------------------------------------------------------------------------- #
# Context container — CONCRETE. Every field is optional so a report can be
# built from a partial pipeline run (a missing stage renders as "not run").
# Extend by adding new Optional fields; renderers already tolerate None.
# --------------------------------------------------------------------------- #

@dataclass
class EdaContext:
    """Everything the report needs, aggregated from the upstream stages."""

    dataset_name: str
    cleaned_csv_path: Optional[Path] = None

    data_prep: Optional["DataPrepResponse"] = None

    univariate: Optional["UnivariateAnalysisResponse"] = None
    univariate_charts: list[Path] = field(default_factory=list)

    multivariate: Optional["MultivariateAnalysisResponse"] = None
    multivariate_charts: list[Path] = field(default_factory=list)

    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    @property
    def all_charts(self) -> list[Path]:
        """Every chart image collected across analysis stages, in order."""
        return [*self.univariate_charts, *self.multivariate_charts]


def collect_context(
    *,
    dataset_name: str,
    cleaned_csv_path: str | Path | None = None,
    data_prep: "DataPrepResponse | None" = None,
    univariate: "UnivariateAnalysisResponse | None" = None,
    univariate_charts: list[Path] | None = None,
    multivariate: "MultivariateAnalysisResponse | None" = None,
    multivariate_charts: list[Path] | None = None,
) -> EdaContext:
    """
    Package the outputs of the upstream stages into a single `EdaContext`.

    CONCRETE: this is just structured aggregation — no LLM call. Pass whatever
    stages have run; the rest default to "not run".
    """
    return EdaContext(
        dataset_name=dataset_name,
        cleaned_csv_path=Path(cleaned_csv_path) if cleaned_csv_path else None,
        data_prep=data_prep,
        univariate=univariate,
        univariate_charts=list(univariate_charts or []),
        multivariate=multivariate,
        multivariate_charts=list(multivariate_charts or []),
    )


# --------------------------------------------------------------------------- #
# Structured narrative — the shape the LLM returns. Mirrors the other agents'
# `ReasoningStep` convention (phase/observation/action).
# --------------------------------------------------------------------------- #

ReportPhase = Literal[
    "ingest_context", "read_charts", "synthesize", "cross_stage", "caveats",
]


class ReasoningStep(BaseModel):
    phase: ReportPhase = Field(description="Which report-synthesis phase this step belongs to.")
    observation: str = Field(description="What was observed from the context/images in this phase.")
    action: str = Field(description="What the writer did with that observation.")


class ChartFinding(BaseModel):
    """One chart's narrative, keyed to the image so it can be paired in assembly."""

    chart_filename: str = Field(
        description="Exact filename (basename) of the attached chart this finding describes."
    )
    finding: str = Field(
        description="What the chart shows (visual reading) and why it matters."
    )


class EdaReportResponse(BaseModel):
    """Structured narrative the assembler stitches into the final markdown."""

    reasoning_steps: list[ReasoningStep] = Field(
        description="Ordered synthesis reasoning, one entry per report phase."
    )
    executive_summary: str = Field(
        description="3-5 sentences of decision-useful headline findings across all stages."
    )
    data_prep_narrative: str = Field(
        description="What was cleaned/normalized and why it matters for trusting the analysis."
    )
    univariate_findings: list[ChartFinding] = Field(
        description="One finding per attached univariate chart, keyed by chart_filename."
    )
    multivariate_findings: list[ChartFinding] = Field(
        description="One finding per attached multivariate chart (incl. the heatmap)."
    )
    cross_stage_insights: str = Field(
        description="Insights connecting univariate and multivariate observations."
    )
    assumptions_and_limitations: list[str] = Field(
        description="Consolidated, deduped assumptions/limitations across every stage."
    )


def _empty_narrative() -> EdaReportResponse:
    """A no-op narrative used when there is nothing to synthesize (offline skeleton)."""
    return EdaReportResponse(
        reasoning_steps=[],
        executive_summary="",
        data_prep_narrative="",
        univariate_findings=[],
        multivariate_findings=[],
        cross_stage_insights="",
        assumptions_and_limitations=[],
    )


# --------------------------------------------------------------------------- #
# LLM narrative synthesis — CONCRETE. One multimodal call: serialized per-stage
# context as text + the chart PNGs as images -> structured EdaReportResponse.
# --------------------------------------------------------------------------- #

def _encode_image(path: Path) -> str:
    """Return a base64 data URL for a PNG so it can ride in the Responses input."""
    encoded = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _serialize_context_for_llm(context: EdaContext) -> str:
    """
    Build the tagged TEXT bundle handed to the model, in the house `<...>` style.

    Includes a fresh profile + correlation report of the cleaned CSV (reusing the
    same helpers the analysis agents use) and each stage's structured response as
    JSON, minus the `code` field — the model writes prose, not code review; the
    generated code goes only into the deterministic appendix.
    """
    parts: list[str] = []

    csv_path = context.cleaned_csv_path
    if csv_path and Path(csv_path).exists():
        try:
            parts.append(f"<dataset_profile>\n{profile_dataset(csv_path)}\n</dataset_profile>")
        except Exception as exc:  # profiling is best-effort context, never fatal here
            parts.append(f"<dataset_profile>\n(profile unavailable: {exc})\n</dataset_profile>")
        try:
            parts.append(
                f"<correlation_report>\n{correlation_profile(csv_path)}\n</correlation_report>"
            )
        except Exception as exc:
            parts.append(
                f"<correlation_report>\n(correlation report unavailable: {exc})\n</correlation_report>"
            )

    if context.data_prep is not None:
        parts.append(
            f"<data_prep>\n{context.data_prep.model_dump_json(exclude={'code'}, indent=2)}\n</data_prep>"
        )
    if context.univariate is not None:
        parts.append(
            f"<univariate>\n{context.univariate.model_dump_json(exclude={'code'}, indent=2)}\n</univariate>"
        )
    if context.multivariate is not None:
        parts.append(
            f"<multivariate>\n{context.multivariate.model_dump_json(exclude={'code'}, indent=2)}\n</multivariate>"
        )

    return "\n\n".join(parts)


def _build_input_parts(context: EdaContext) -> list[dict]:
    """
    Assemble the multimodal user message: the text bundle first, then each chart
    as a captioned image so the model can associate a finding with its filename.
    """
    content: list[dict] = [
        {"type": "input_text", "text": _serialize_context_for_llm(context)}
    ]
    for stage, charts in (
        ("Univariate", context.univariate_charts),
        ("Multivariate", context.multivariate_charts),
    ):
        for chart in charts:
            path = Path(chart)
            if not path.exists():
                continue
            try:
                data_url = _encode_image(path)
            except Exception:
                continue  # skip unreadable images rather than aborting the report
            content.append({"type": "input_text", "text": f"{stage} chart [{path.name}]:"})
            content.append({"type": "input_image", "image_url": data_url})

    return [{"role": "user", "content": content}]


def generate_report_narrative(
    context: EdaContext,
    model: str = OPENAI_MODEL,
) -> EdaReportResponse:
    """
    Produce the structured report narrative from the aggregated context.

    Single-turn synthesis (no code executes, so no self-correction loop). When no
    analysis stage ran, short-circuits to an empty narrative WITHOUT an API call so
    the offline skeleton smoke test needs neither key nor network.
    """
    if not (context.data_prep or context.univariate or context.multivariate):
        return _empty_narrative()

    response = client.responses.parse(
        model=model,
        instructions=REPORT_INSTRUCTIONS,
        input=_build_input_parts(context),
        reasoning={"context": "current_turn", "effort": "high"},
        text_format=EdaReportResponse,
    )
    if response.output_parsed is None:
        raise RuntimeError(
            f"Report synthesis did not produce a parsed result: {response.output_text}"
        )
    return response.output_parsed


# --------------------------------------------------------------------------- #
# Section renderers — CONCRETE. Each takes the context, the LLM narrative, and
# the report directory, and returns its markdown block. Add a section by writing
# one renderer and appending it to `_SECTION_RENDERERS`.
# --------------------------------------------------------------------------- #

def _md_image_link(image_path: Path, report_dir: Path) -> str:
    """Markdown image embed with a path relative to the report location."""
    rel = os.path.relpath(Path(image_path).resolve(), report_dir.resolve())
    rel = rel.replace(os.sep, "/")
    return f"![{Path(image_path).stem}]({rel})"


def _match_finding(findings: list[ChartFinding], chart: Path) -> Optional[ChartFinding]:
    """Find the ChartFinding whose filename matches a chart path (case-insensitive)."""
    name = Path(chart).name.strip().lower()
    for finding in findings:
        if finding.chart_filename.strip().lower() == name:
            return finding
    return None


def _render_header(context: EdaContext, narrative: EdaReportResponse, report_dir: Path) -> str:
    return (
        f"# EDA Report — {context.dataset_name}\n\n"
        f"_Generated: {context.generated_at}_\n\n"
        f"Cleaned dataset: `{context.cleaned_csv_path}`\n"
    )


def _render_executive_summary(context: EdaContext, narrative: EdaReportResponse, report_dir: Path) -> str:
    body = narrative.executive_summary.strip() or "_No analysis stages were run._"
    return f"## Executive Summary\n\n{body}\n"


def _render_data_prep_section(context: EdaContext, narrative: EdaReportResponse, report_dir: Path) -> str:
    lines = ["## 1. Data Preparation\n"]
    if context.data_prep is None:
        lines.append("_Stage not run._\n")
        return "\n".join(lines)

    prep = context.data_prep
    lines.append(f"**Summary:** {prep.summary}\n")
    lines.append(f"- Detected date column: `{prep.detected_date_column}`")
    lines.append(f"- Derived columns: {', '.join(prep.derived_columns) or '—'}")
    lines.append(f"- Dropped columns: {', '.join(prep.dropped_columns) or '—'}\n")
    if narrative.data_prep_narrative.strip():
        lines.append(narrative.data_prep_narrative.strip() + "\n")
    return "\n".join(lines)


def _render_univariate_section(context: EdaContext, narrative: EdaReportResponse, report_dir: Path) -> str:
    lines = ["## 2. Univariate Analysis\n"]
    if context.univariate is None:
        lines.append("_Stage not run._\n")
        return "\n".join(lines)

    lines.append(f"**Summary:** {context.univariate.summary}\n")
    for chart in context.univariate_charts:
        lines.append(_md_image_link(chart, report_dir) + "\n")
        finding = _match_finding(narrative.univariate_findings, chart)
        if finding and finding.finding.strip():
            lines.append(finding.finding.strip() + "\n")
    return "\n".join(lines)


def _render_multivariate_section(context: EdaContext, narrative: EdaReportResponse, report_dir: Path) -> str:
    lines = ["## 3. Multivariate Analysis\n"]
    if context.multivariate is None:
        lines.append("_Stage not run._\n")
        return "\n".join(lines)

    lines.append(f"**Summary:** {context.multivariate.summary}\n")
    for chart in context.multivariate_charts:
        lines.append(_md_image_link(chart, report_dir) + "\n")
        finding = _match_finding(narrative.multivariate_findings, chart)
        if finding and finding.finding.strip():
            lines.append(finding.finding.strip() + "\n")
    return "\n".join(lines)


def _render_cross_stage_insights(context: EdaContext, narrative: EdaReportResponse, report_dir: Path) -> str:
    body = narrative.cross_stage_insights.strip() or "_Not available._"
    return f"## 4. Cross-Stage Insights\n\n{body}\n"


def _render_assumptions_and_limitations(context: EdaContext, narrative: EdaReportResponse, report_dir: Path) -> str:
    lines = ["## 5. Assumptions & Limitations\n"]
    if narrative.assumptions_and_limitations:
        for item in narrative.assumptions_and_limitations:
            if item.strip():
                lines.append(f"- {item.strip()}")
        lines.append("")
    else:
        lines.append("_None recorded._\n")
    return "\n".join(lines)


def _render_appendix(context: EdaContext, narrative: EdaReportResponse, report_dir: Path) -> str:
    lines = ["## Appendix — Generated Code\n"]
    stages = [
        ("Data Preparation", context.data_prep),
        ("Univariate", context.univariate),
        ("Multivariate", context.multivariate),
    ]
    any_code = False
    for title, response in stages:
        code = getattr(response, "code", "") if response is not None else ""
        if code and code.strip():
            any_code = True
            lines.append(f"### {title}\n")
            lines.append("```python")
            lines.append(code.rstrip())
            lines.append("```\n")
    if not any_code:
        lines.append("_No generated code available._\n")
    return "\n".join(lines)


# Ordered section pipeline. Append a new renderer here to add a section.
_SECTION_RENDERERS: list[Callable[[EdaContext, EdaReportResponse, Path], str]] = [
    _render_header,
    _render_executive_summary,
    _render_data_prep_section,
    _render_univariate_section,
    _render_multivariate_section,
    _render_cross_stage_insights,
    _render_assumptions_and_limitations,
    _render_appendix,
]


# --------------------------------------------------------------------------- #
# Assembly + persistence — CONCRETE.
# --------------------------------------------------------------------------- #

def assemble_report(context: EdaContext, report_dir: Path) -> str:
    """Synthesize the narrative once, then walk the section renderers into markdown."""
    narrative = generate_report_narrative(context)
    sections = [render(context, narrative, report_dir) for render in _SECTION_RENDERERS]
    return "\n\n".join(sections).rstrip() + "\n"


def write_report(markdown: str, output_path: str | Path) -> Path:
    """Write the markdown report to disk and return the path."""
    output_file = Path(output_path).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(markdown, encoding="utf-8")
    return output_file


def run_report(
    context: EdaContext,
    output_path: str | Path | None = None,
) -> Path:
    """
    End-to-end report step: assemble the markdown from context and write it.

    Returns the path to the written report.
    """
    if output_path is None:
        output_path = REPORTS_DIR / f"{context.dataset_name}_eda_report.md"
    output_path = Path(output_path)

    markdown = assemble_report(context, report_dir=output_path.parent)
    return write_report(markdown, output_path)


if __name__ == "__main__":
    # Smoke test: an empty-ish context still yields a valid, skeletal report so
    # the structure can be reviewed before any stage output exists. With no stages
    # present, narrative synthesis short-circuits and makes no API call.
    demo_context = collect_context(dataset_name="sales_data")
    report_path = run_report(demo_context)
    print(f"Skeleton report written to: {report_path}")
