# EDA Agent Pipeline — Execution Architecture

## Diagram

```mermaid
flowchart TD
    A["Raw CSV\n(agentic_eda/data/sales_data.csv)"] --> B["Data Prep Agent\ndata_prep/agent.py"]

    B -->|"cleaned CSV\noutputs/cleaned/*.csv"| C["Univariate Agent\nunivariate_analysis/agent.py"]
    B -->|"cleaned CSV\noutputs/cleaned/*.csv"| D["Multivariate Agent\nmultivariate_analysis/agent.py"]

    C -->|"structured result\n+ chart PNGs"| E["Report Agent\nreport/agent.py"]
    D -->|"structured result\n+ chart PNGs"| E

    E --> F["Markdown Report\noutputs/reports/*.md"]

    subgraph P [" Independent — same input, no shared state "]
        C
        D
    end
```

## What each step does

| Step | Module | Input | LLM call | Subprocess execution | Output |
|---|---|---|---|---|---|
| **1. Data Prep** | `data_prep/agent.py` | Raw CSV profile | Reasons about nulls/types/dates, generates pandas cleaning code | Runs the generated code in isolation | Cleaned CSV |
| **2a. Univariate** | `univariate_analysis/agent.py` | Cleaned CSV profile | **Multi-turn:** Turn 1 plans charts per variable; Turn 2 generates matplotlib code | Runs the code in a headless (`Agg`) subprocess with bounded self-correction loops | One PNG per selected variable → `outputs/charts/univariate/` |
| **2b. Multivariate** | `multivariate_analysis/agent.py` | Cleaned CSV profile + correlation report | **Multi-turn:** Turn 1 selects relationships clearing the correlation threshold; Turn 2 generates matplotlib code | Runs the code in a headless subprocess with bounded self-correction loops | One PNG per selected relationship + correlation heatmap → `outputs/charts/multivariate/` |
| **3. Report** | `report/agent.py` | Structured results + chart images from steps 1, 2a, 2b | **Single multimodal call:** reasons over the stage reports and visual charts to synthesize narrative findings | — (no code generated) | Markdown report assembled deterministically → `outputs/reports/` |

### Key Architectural Concepts

#### Configurable Models per Agent
Instead of enforcing a single, uniform model across all agents, each agent defines its own local client configuration and target model (`OPENAI_MODEL` in its respective `agent.py`). This offers several design benefits:
- **Cost & Speed Optimization**: Simpler task stages (like Data Prep or Univariate charting) can run on faster, cheaper models (like `gpt-4o-mini`).
- **Targeted Capabilities**: The final report step can be targeted at a highly capable multimodal model (like `gpt-4o`) to visually interpret the charts, while other steps focus purely on text and code generation.
- **Granular Tuning**: Model choices can be experimented with or swapped out for individual agents without risking or modifying the stability of other pipeline stages.

#### Purpose of each stage
- **Data Prep**: Standardizes the schema (forces `Year/Month/Day/Hour` columns, correct dtypes) so downstream agents don't waste context or code handling validation and type parsing.
- **Univariate**: Focuses on individual columns. It uses a **multi-turn conversation** to separate the planning stage (chart type selection, grounding in profile) from code generation, making the pipeline's plan inspectable before code runs.
- **Multivariate**: Investigates pairwise column relations (e.g. numeric↔numeric and numeric↔categorical). A correlation matrix is precalculated deterministically in Python to guide the selection turn, preventing the LLM from plotting uninformative relationships.
- **Multi-turn Reasoning Continuity**: For the analysis agents, turns are sent with `store=True` and chained using `previous_response_id` so OpenAI handles conversation context server-side. If a generated script fails, `stderr` is fed back as a correction turn.
- **Per-item Isolation**: Generated code wraps each chart's rendering in its own `try/except` block, ensuring that one faulty column or category relationship does not break the entire pipeline execution.
- **Report Synthesis**: The report agent acts as a multimodal join-point. It reads the final charts visually and returns structured narrative findings. Python then assembles the markdown document layout deterministically, ensuring robust link and file output paths.

## Parallel Execution Potential

Although the pipeline runs sequentially today, it is structurally designed for parallel execution. The Data Prep stage acts as a bottleneck, but once the cleaned dataset is written, the Univariate and Multivariate analysis stages are completely independent of each other:

```mermaid
flowchart LR
    A["Data Prep<br>(data_prep/agent.py)"] --> B["Univariate Analysis<br>(univariate_analysis/agent.py)"]
    A --> C["Multivariate Analysis<br>(multivariate_analysis/agent.py)"]
    B --> D["Report Synthesis<br>(report/agent.py)"]
    C --> D
```

### Execution Details
- **Current Sequential Pipeline**: In `pipeline.py`, the stages run sequentially (`Data Prep` -> `Univariate` -> `Multivariate` -> `Report`). This makes logs straightforward to follow and simplifies tracing OpenAI API response states and stdout/stderr output.
- **Parallelization Capabilities**: Because both Univariate and Multivariate analysis are I/O-bound (each calls its own target OpenAI model and executes generated python code in a child subprocess) and share no state, they are fully concurrently runnable. The pipeline can be parallelized (e.g., utilizing `asyncio.gather` or a thread pool in `pipeline.py`) to reduce the total processing time by letting both analysis stages execute simultaneously.
- **Report Synthesis Join-Point**: The Report stage serves as a synchronization join-point. It cannot begin execution until both Univariate and Multivariate analysis have completed and generated their respective charts and structured analysis outputs.

---

## Second Consumer: the Streaming Web Server

`pipeline.py` is no longer the only orchestrator. `server/services/orchestrator.py`
drives the same four agents for the web app. They are deliberate siblings rather
than one shared function: the CLI wants `print` output and the flat `outputs/`
paths, while the server wants structured events and per-run isolation. Forcing one
function to serve both would have compromised each. What *is* shared is everything
that matters — the same four agent entrypoints, the same executors, the same
profiler, the same `config.py` paths.

```mermaid
flowchart TD
    subgraph CLIENT ["Browser — React + TypeScript"]
        UP["Upload CSV"] --> TRIG["Manual trigger"]
        SSE["EventSource<br>/api/runs/{id}/events"] --> RED["runReducer<br>seq-based dedup"]
        RED --> UI["Stage timeline · reasoning ·<br>plan tables · charts · report"]
    end

    TRIG -->|"POST /api/runs → 202"| RM
    subgraph SERVER ["FastAPI — :8000"]
        RM["RunManager<br>ThreadPoolExecutor(max 2)"]
        ORCH["Orchestrator<br>4 stages, blocking"]
        HUB["EventHub<br>history + subscribers"]
        LOG[("events.jsonl")]
        RM --> ORCH
        ORCH -->|"emit() via<br>call_soon_threadsafe"| HUB
        HUB --> LOG
        HUB --> SSE
    end

    ORCH --> AGENTS["The four agents<br>(unchanged, + on_event hook)"]
    AGENTS --> ART[("outputs/runs/{run_id}/<br>charts · cleaned · reports")]
    ART -->|"/artifacts/..."| UI
```

### The three problems the server had to solve

**1. Everything is blocking.** No agent is async: `client.responses.parse`,
`subprocess.run`, and multi-second `pd.read_csv` calls would all freeze the event
loop for minutes. So a run is submitted to a `ThreadPoolExecutor`, and the worker
thread marshals events back onto the loop with `loop.call_soon_threadsafe`. All
mutation of the event history and subscriber queues therefore stays
single-threaded, and no locking is needed.

A useful consequence falls out of putting the work in the executor rather than in a
request handler: **a client disconnect cannot cancel a run**. Given that a run costs
4–12 minutes and real API spend, surviving a closed tab is the correct behaviour.

**2. Stages are silent for minutes.** Wrapping only the four public functions would
yield about ten events across a twelve-minute run — long enough that the UI would
read as hung. Each agent entrypoint therefore takes an optional
`on_event(name, payload)` hook, defaulting to a no-op so the CLI and notebook are
untouched. With it, the stream carries sub-stage detail: profiling, turn 1 of 2,
turn 2 of 2, subprocess execution, and each self-correction retry. The agents emit
short `(name, payload)` pairs and know nothing about the wire envelope; the
orchestrator stamps the stage and maps names to event types.

**3. Concurrent runs corrupted each other.** `execute_chart_generation_code`
identifies the PNGs it produced by globbing `charts_dir` and filtering on mtime.
Two runs sharing that directory each pick up the other's charts. Because all four
entrypoints already accepted `charts_dir` / `output_csv_path` / `output_path`, the
fix needed no agent change: the server allocates `outputs/runs/{run_id}/` per run
and passes those paths explicitly.

### Resumability

Every event carries a monotonic `seq`, emitted as the SSE frame's `id`. That single
decision buys three behaviours with no bespoke protocol work:

- **Reconnection** — browser `EventSource` retries automatically and resends
  `Last-Event-ID`; the server replays only events after it.
- **Idempotence** — the client discards any `seq` it has already applied, so
  replayed history and a second browser tab are both harmless.
- **Durability** — the same events are appended to `events.jsonl`, which powers
  post-restart inspection and a replay mode that re-streams a finished run with
  zero OpenAI calls.

Heartbeats every 10s deliberately reuse the last real `seq`, so a long quiet stage
never advances the client's dedup cursor.

### Honest limits

- **Cancellation is cooperative.** A blocking `responses.parse` cannot be
  interrupted, so the cancel flag is only checked between stages; the executing
  stage finishes.
- **Run state is in memory**, mirrored to `run.json`. After a restart, completed
  runs stay inspectable and replayable, but runs that were in flight are reported
  as failed rather than silently left "running".
- **The report's markdown keeps relative image links** (`../charts/univariate/*.png`)
  so the file stays correct on disk. The API returns a `base_url` alongside the
  markdown and the client resolves each `src` against it, rather than the server
  rewriting the document.
