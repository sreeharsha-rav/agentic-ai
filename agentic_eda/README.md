# Agentic EDA — Sales Data Explorer

An LLM-powered, multi-agent pipeline that takes a raw CSV data and produces a complete exploratory data analysis: cleaned dataset, univariate & multivariate charts, and a synthesized markdown report — fully automated via OpenAI Structured Outputs.

Dataset: [Kaggle - Sales CSV](https://www.kaggle.com/datasets/beekiran/sales-data-analysis)

## How It Works

The pipeline runs four specialised agents in sequence, each grounded in a real profile of the data rather than LLM guesses:

```
Raw CSV  →  Data Prep  →  Cleaned CSV  →  Univariate ──┐
                                        →  Multivariate ─┤→  Report Agent  →  Markdown Report
```

| # | Agent | What it does | Output |
|---|---|---|---|
| 1 | **Data Prep** | Profiles raw CSV, LLM reasons about nulls / types / dates, generates & runs a pandas cleaning script. Mandatory: `Year`, `Month`, `Day`, `Hour` derived columns. | `outputs/cleaned/<name>_cleaned.csv` |
| 2a | **Univariate** | **Multi-turn:** Turn 1 profiles the cleaned CSV and plans one chart per variable (histogram / bar / top-N) or skips it; Turn 2 generates matplotlib code for exactly those. Reasoning carries across turns via `previous_response_id`; execution failures are self-corrected in bounded retries. | `outputs/charts/univariate/*.png` |
| 2b | **Multivariate** | **Multi-turn:** Turn 1 reasons over a precomputed correlation report and selects pairwise relationships (numeric↔numeric, numeric↔categorical) + a correlation heatmap; Turn 2 generates matplotlib code for exactly those. Same reasoning-continuity and self-correction as Univariate. Runs in parallel with Univariate logically; currently sequential in `pipeline.py`. | `outputs/charts/multivariate/*.png` |
| 3 | **Report** | **Multimodal synthesis:** serializes every prior stage's context (profile, correlation report, plans, reasoning, summaries) and attaches the chart PNGs as images, so the model reads the charts visually and returns structured narrative (executive summary, per-chart findings, cross-stage insights, consolidated assumptions). Python assembles that into the final markdown — image links + generated-code appendix. | `outputs/reports/<name>_report.md` |

All generated code runs in an **isolated subprocess** (never `exec()`), with timeout enforcement and output-existence checks for safety — see `executors.py`.

## Project Structure

```
agentic_eda/
├── .env                         # API key (not committed)
├── .env.sample                  # Sample environment file configuration
├── ARCHITECTURE.md              # Pipeline diagram and design notes
├── README.md                    # This documentation file
├── config.py                    # Paths, correlation threshold, env loading (no shared client/model)
├── pipeline.py                  # End-to-end orchestrator (run this)
├── data/                        # Raw dataset directory
│   └── sales_data.csv           # Raw sales CSV dataset
├── data_prep/                   # Step 1 — Cleaning Agent module
│   ├── __init__.py
│   ├── agent.py                 # Cleaning agent execution logic
│   └── prompts.py               # Cleaning system instructions
├── univariate_analysis/         # Step 2a — Univariate Analysis Agent module (multi-turn)
│   ├── __init__.py
│   ├── agent.py                 # Per-variable analysis/plotting execution logic
│   └── prompts.py               # Univariate analysis prompts
├── multivariate_analysis/       # Step 2b — Multivariate Analysis Agent module (multi-turn)
│   ├── __init__.py
│   ├── agent.py                 # Pairwise relationship selection/plotting logic
│   └── prompts.py               # Multivariate analysis prompts
├── report/                      # Step 3 — Multimodal Report Agent module (single-turn vision)
│   ├── __init__.py
│   ├── agent.py                 # Narrative synthesis & assembly logic
│   └── prompts.py               # Report synthesis prompts
├── utils/                       # Shared helper utilities
│   ├── __init__.py
│   ├── executors.py             # Isolated subprocess runner with safety guards
│   └── profiling.py             # Shared CSV profiler (schema, correlation matrix)
└── outputs/                     # Generated run artifacts (auto-created)
    ├── cleaned/                 # Cleaned/normalized CSVs from Step 1
    ├── charts/
    │   ├── univariate/          # Output PNG charts from Step 2a
    │   └── multivariate/        # Output PNG charts from Step 2b
    └── reports/                 # Synthesized Markdown reports from Step 3
```

## Data

Place the raw sales CSV under:

```
agentic_eda/data/sales_data.csv
```

`config.py` resolves this automatically from `BASE_DIR / "data"`.  
Dataset expected: ~185 k rows, columns include `Order ID`, `Product`, `Quantity Ordered`, `Price Each`, `Order Date`, `Purchase Address`, `Month`, `Sales`, `City`, `Hour`.

## Environment Setup

### 1. Install dependencies

From the **project root** (requires [uv](https://github.com/astral-sh/uv) or pip):

```bash
# uv (recommended)
uv sync
uv add openai python-dotenv pandas matplotlib

# or pip
pip install openai python-dotenv pandas matplotlib
```

### 2. Configure the API key

Create `agentic_eda/.env`:

```dotenv
OPENAI_API_KEY=sk-proj-...your-key-here...
```

`config.py` loads this file automatically via `load_dotenv(dotenv_path=BASE_DIR / ".env")`.

> **Note:** The `.env` file is gitignored. Never commit your API key.

### 3. Model

Each agent defines its own `client = OpenAI(api_key=OPENAI_API_KEY)` and `OPENAI_MODEL` constant locally in its respective `agent.py` file rather than sharing one from `config.py` — this lets each stage be pointed at a different model independently, e.g. for isolated testing. Update the `OPENAI_MODEL` value at the top of the relevant agent file (`agentic_eda/data_prep/agent.py`, `agentic_eda/univariate_analysis/agent.py`, etc.) to any model that supports **Structured Outputs / `responses.parse()`** with reasoning (required for the multi-turn agents). The **report agent additionally needs a vision-capable model**, since it reads the chart images.

## Running the Pipeline

Run the full end-to-end pipeline from the project root:

```bash
# Default — uses agentic_eda/data/sales_data.csv
python -m agentic_eda.pipeline

# Custom CSV
python -m agentic_eda.pipeline path/to/your_data.csv
```

Run an individual agent:

```bash
python -m agentic_eda.data_prep.agent
python -m agentic_eda.univariate_analysis.agent
python -m agentic_eda.multivariate_analysis.agent
python -m agentic_eda.report.agent
```

Outputs are written to `agentic_eda/outputs/` and are self-contained within this module.

## Key Design Decisions

- **Structured Outputs** — every agent response is validated against a Pydantic schema, guaranteeing fields like `reasoning_steps`, `code`, and `summary` are always present and correctly typed.
- **Subprocess isolation** — LLM-generated code is untrusted; running it in a child process with a timeout and output-existence check is the safety boundary.
- **Profile-first** — agents receive a real `df.info()` + null counts + cardinality + head preview, so the LLM reasons over actual data rather than hallucinated schema.
- **Fan-out / fan-in** — Univariate and Multivariate are logically independent (both only read the cleaned CSV); they can be parallelised with `asyncio.gather` or a thread pool without changing their APIs.
- **Multi-turn, not one-shot** — Univariate and Multivariate each split into a SELECTION turn (decide what to plot, grounded in the real profile / correlation numbers, no code) and a CODE-GEN turn (given that plan, write the matplotlib script). This keeps chart selection auditable independently of the generated code and avoids overloading a single prompt with both jobs.
- **Server-side reasoning continuity** — turns are sent with `store=True`, and each subsequent turn (including fix retries) passes the prior response's `id` as `previous_response_id`, so OpenAI carries the reasoning context forward without the caller replaying history manually.
- **Self-correcting on execution failure** — if the generated script raises in the subprocess, the traceback is sent back as a new turn chained onto the failed response, prompting the model to diagnose the root cause, scan the rest of the script for the same class of mistake, and return a corrected full script — bounded by `max_fix_attempts` before the error propagates to the caller.
- **Per-item error isolation in generated code** — each chart (per variable, or per relationship/heatmap) is wrapped in its own `try/except` in the generated script, so one bad column or pair can't abort the whole run.
- **Report = multimodal synthesis, Python owns layout** — the report agent sends the model both the serialized per-stage context and the actual chart images, but the LLM only returns *narrative* (structured per-section prose + per-chart findings). Python deterministically assembles the markdown, computes report-relative image paths, and embeds the generated-code appendix — so image paths and document structure are never left to the model to guess.
