# Agentic AI

A repo for agentic ai workflows.

## Pre-Requisites

- Python 3.12+
- `uv`
- Google AI Studio with Gemini API Key
- OpenAI Account with API Key

## Setup

1. Create a Python environment:
    ```bash
    uv venv
    ```

2. Activate the environment:
    ```bash
    uv venv
    ```
    *Windows*
    ```bash
    .\.venv\Scripts\activate
    ```
    *Linux/Mac*
    ```bash
    source .venv/bin/activate
    ```

3. Install dependencies:
    ```bash
    uv sync
    ```

## Agents

### [Google ADK Tutorial](./adk_tut_1)

Basic agent for tutorial developed using Google ADK.

### [Agentic Exploratory Data Analysis](./agentic_eda)

This is an agent based EDA framework that helps to do EDA on a given dataset.

Four LLM agents — data prep, univariate, multivariate, report — turn a raw CSV into
a cleaned dataset, charts and a synthesized markdown report. Run it three ways:

```bash
python -m agentic_eda.pipeline                              # CLI, end to end
jupyter lab agentic_eda/workflow.ipynb                      # step by step
uv run uvicorn agentic_eda.server.main:app --reload         # web app (+ pnpm dev in agentic_eda/web)
```

The web app streams every agent's reasoning, generated code, charts and retries live
over Server-Sent Events. See [agentic_eda/README.md](./agentic_eda/README.md#web-application).
