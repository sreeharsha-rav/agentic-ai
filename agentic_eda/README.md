# Agentic EDA — Sales Data Explorer

An LLM-powered, multi-agent pipeline that takes raw CSV data and produces a complete exploratory data analysis: a cleaned dataset, univariate & multivariate charts, and a synthesized markdown report. Fully automated via OpenAI Structured Outputs.

For in-depth details on the pipeline's execution flow and design decisions, refer to the [Architecture Document](./ARCHITECTURE.md).

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

## Setup Instructions

### 1. Download Dataset
Download the [Kaggle - Sales CSV](https://www.kaggle.com/datasets/beekiran/sales-data-analysis) dataset and place the CSV file at:
```
agentic_eda/data/sales_data.csv
```

### 2. Install Dependencies
From the repository root directory, run:
```bash
# Using uv (recommended)
uv sync
uv add openai python-dotenv pandas matplotlib

# Or using pip
pip install openai python-dotenv pandas matplotlib
```

### 3. Configure API Key
Create a `.env` file in the `agentic_eda/` directory:
```dotenv
OPENAI_API_KEY=sk-proj-...your-key-here...
```

### 4. Configure Models (Optional)
Each agent defines its own `OPENAI_MODEL` constant in its respective `agent.py` file. Update these values to configure models supporting **Structured Outputs** (e.g. `gpt-4o` / `gpt-4o-mini`). The **report agent** (`agentic_eda/report/agent.py`) requires a vision-capable model to inspect generated charts.

---

## Running the Pipeline

### End-to-End Orchestrator
Execute the complete multi-agent pipeline with:
```bash
# Run with the default sales dataset
python -m agentic_eda.pipeline

# Or run with a custom CSV dataset
python -m agentic_eda.pipeline path/to/your_data.csv
```

### Individual Agents
Run any step individually (e.g., for testing):
```bash
python -m agentic_eda.data_prep.agent
python -m agentic_eda.univariate_analysis.agent
python -m agentic_eda.multivariate_analysis.agent
python -m agentic_eda.report.agent
```
All outputs are stored under `agentic_eda/outputs/`.

---

## Design Decisions (Brief)

- **Structured Outputs & Pydantic**: Every agent response is strongly validated against a Pydantic schema for reliable behavior.
- **Subprocess Isolation**: Generated Python code is executed in isolated child processes with timeout boundaries for safety.
- **Profile-First Grounding**: Agents are fed real dataset metadata (data profile & correlations) instead of relying on LLM guesses.
- **Multi-Turn Planning**: Analysis agents split work into separate SELECTION (planning) and CODE-GEN (generation) turns for auditable execution.
- **Server-Side Context Continuity**: Chained calls use OpenAI's `store=True` and `previous_response_id` to carry forward conversation context.
- **Self-Correction & Error Isolation**: Code execution tracebacks are fed back to agents for bounded self-healing. Each chart generation block is wrapped in a `try/except` to ensure one error does not fail the entire run.
- **Deterministic Presentation & Multimodal Synthesis**: Presentation layout and Markdown structure are handled deterministically by Python. The report agent uses visual readings of the generated charts to write narrative insights.
