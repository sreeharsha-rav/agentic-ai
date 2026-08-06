# Agentic EDA — Sales Data Explorer

An LLM-powered, multi-agent pipeline that takes raw CSV data and produces a complete exploratory data analysis: a cleaned dataset, univariate & multivariate charts, and a synthesized markdown report. Fully automated via OpenAI Structured Outputs.

Three ways to run it: an **end-to-end CLI**, a **step-by-step notebook**, and a **fullstack web app** that streams every agent's progress live over Server-Sent Events.

For in-depth details on the pipeline's execution flow and design decisions, refer to the [Architecture Document](./ARCHITECTURE.md).

## Project Structure

```
agentic_eda/
├── .env                         # API key (not committed)
├── .env.sample                  # Sample environment file configuration
├── ARCHITECTURE.md              # Pipeline diagram and design notes
├── README.md                    # This documentation file
├── config.py                    # Paths, correlation threshold, env loading (no shared client/model)
├── pipeline.py                  # End-to-end CLI orchestrator (run this)
├── workflow.ipynb               # Step-by-step interactive Jupyter Notebook
├── data/                        # Raw dataset directory
│   ├── sales_data.csv           # Raw sales CSV dataset
│   └── uploads/                 # CSVs uploaded through the web app (auto-created)
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
├── server/                      # FastAPI streaming backend
│   ├── __init__.py
│   ├── main.py                  # App factory: CORS, /artifacts mount, routers, lifespan
│   ├── settings.py              # Upload caps, concurrency, heartbeat, replay pacing
│   ├── smoke_test.py            # Manual smoke test (no OpenAI calls) — you run this
│   ├── api/
│   │   ├── datasets.py          # POST/GET /api/datasets — chunked upload + profiling
│   │   └── runs.py              # Run control + the SSE event stream
│   ├── models/
│   │   ├── events.py            # EventType, EventEnvelope, stage metadata
│   │   └── schemas.py           # Request/response + snapshot schemas
│   └── services/
│       ├── storage.py           # Per-run directories, upload persistence, path→URL
│       ├── event_hub.py         # Per-run history, subscriber queues, events.jsonl
│       ├── orchestrator.py      # The 4-stage sequence, calls agents with on_event
│       ├── run_manager.py       # Registry, thread pool, sync→async bridge, lifecycle
│       └── replay.py            # events.jsonl → paced re-publish (free re-watching)
├── web/                         # React + TypeScript observability dashboard (Vite)
│   ├── package.json, vite.config.ts, tsconfig*.json, index.html
│   └── src/
│       ├── main.tsx, App.tsx
│       ├── styles/              # tokens.css (light/dark), global.css
│       ├── types/events.ts      # Discriminated union mirroring the wire protocol
│       ├── api/                 # client.ts (REST), eventStream.ts (EventSource)
│       ├── state/runReducer.ts  # Projected run state + seq-based dedup
│       ├── hooks/               # useEdaRun (lifecycle), useElapsed (local timers)
│       └── components/          # Timeline, stage cards, plan tables, gallery, report
└── outputs/                     # Generated run artifacts (auto-created)
    ├── cleaned/                 # Cleaned CSVs from Step 1  (CLI + notebook)
    ├── charts/
    │   ├── univariate/          # PNG charts from Step 2a   (CLI + notebook)
    │   └── multivariate/        # PNG charts from Step 2b   (CLI + notebook)
    ├── reports/                 # Markdown reports from Step 3 (CLI + notebook)
    └── runs/                    # One isolated directory per web-app run
        └── <run_id>/
            ├── run.json         # Status snapshot (survives a restart)
            ├── events.jsonl     # Append-only event log (replay + recovery)
            ├── cleaned/
            ├── charts/{univariate,multivariate}/
            └── reports/
```

> **Why `outputs/runs/`?** `execute_chart_generation_code` discovers the PNGs it
> produced by globbing a directory and filtering on mtime. Two concurrent runs
> sharing one `charts_dir` would each claim the other's charts, so the server
> gives every run its own tree. The flat `outputs/{cleaned,charts,reports}`
> directories stay reserved for the CLI and the notebook.

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

# Backend for the web app (already declared in pyproject.toml — `uv sync` covers it)
uv add fastapi "uvicorn[standard]" python-multipart

# Or using pip
pip install openai python-dotenv pandas matplotlib fastapi "uvicorn[standard]" python-multipart
```

> On a network with TLS interception, append `--native-tls` to any `uv` command
> (e.g. `uv sync --native-tls`) if you hit `invalid peer certificate`.

For the frontend (requires Node 18+ and `pnpm`):
```powershell
cd agentic_eda\web
pnpm install
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

### Interactive Jupyter Notebook
For step-by-step analysis, inspecting reasoning chains, and displaying inline chart outputs:
```bash
jupyter lab agentic_eda/workflow.ipynb
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

## Web Application

Upload a CSV, inspect the profile the agents will be grounded on, press a button,
and watch all four agents work in real time — reasoning steps, generated Python,
per-variable decisions, charts appearing one by one, and self-correction retries.

### Running it

Two terminals, from the repository root:

```powershell
# Terminal 1 — FastAPI backend on :8000
uv run uvicorn agentic_eda.server.main:app --reload --port 8000

# Terminal 2 — Vite dev server on :5173
cd agentic_eda\web ; pnpm dev
```

Then open <http://localhost:5173>. Vite proxies `/api` and `/artifacts` to the
backend, so there is no CORS to configure in development.

`--reload` is safe: worker threads and their `subprocess` children live inside the
reloaded worker process, so a reload leaves no orphans. It does abandon an
in-flight run's in-memory state — though its `events.jsonl` survives and can be
replayed.

For a production-style single-origin serve:
```powershell
cd agentic_eda\web ; pnpm build     # emits agentic_eda/web/dist/
```

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/datasets` | Multipart CSV upload, streamed to disk in 1 MB chunks. Returns a `dataset_id` and the plain-text profile. Rejects non-`.csv` (400), oversize (413), unparseable (422). |
| `GET` | `/api/datasets` | Previously uploaded datasets. |
| `POST` | `/api/runs` | **Manual trigger.** `{dataset_id}` for a live run, or `{mode:"replay", source_run_id}`. Returns `202` immediately with `{run_id}`. `429` at the concurrency cap. |
| `GET` | `/api/runs` | Run index, including runs from earlier server processes. |
| `GET` | `/api/runs/{id}` | Full snapshot — rehydrates a reloaded page in one request. |
| `GET` | `/api/runs/{id}/events` | **SSE stream.** Honors `Last-Event-ID`. |
| `POST` | `/api/runs/{id}/cancel` | Cooperative cancel (see caveat below). |
| `GET` | `/api/runs/{id}/report` | `{markdown, base_url}` for rendering the report. |
| `GET` | `/api/health`, `/api/meta/stages` | Config and stage metadata. |
| — | `/artifacts/{run_id}/...` | Static mount over `outputs/runs/` — charts, cleaned CSV, report. |

Interactive API docs at <http://127.0.0.1:8000/docs>.

### Event protocol

Every event is an envelope with a **monotonic `seq`**, which is also the SSE frame
`id`. That is what makes the stream resumable: a reconnecting client sends
`Last-Event-ID` and the server replays only what was missed, while the client
ignores any `seq` it has already applied — so double delivery is harmless.

```
id: 12
event: agent.reasoning
data: {"seq":12,"ts":"...","run_id":"...","type":"agent.reasoning","stage":"univariate","payload":{...}}
```

| `type` | Payload |
|---|---|
| `run.started` | `run_id, dataset_name, mode, stages[]` |
| `stage.started` | `stage, label, expected_seconds` |
| `stage.progress` | `message`, optional `turn`/`of` — e.g. *"turn 2/2: generating matplotlib code"* |
| `agent.profile` | `kind` (`dataset`/`correlation`), `text` — the grounding the agent actually saw |
| `agent.reasoning` | `index, phase, observation, action` — one per reasoning step |
| `agent.turn.completed` | `turn` (`prep`/`selection`/`codegen`/`narrative`), `data` |
| `agent.plan` | `kind` (`variable`/`relationship`), `items[]` — the full decision table, skips included |
| `agent.code` | `language, code`, optional `revision` |
| `agent.retry` | `attempt, max_attempts, error`, `exhausted` |
| `artifact.created` | `kind, filename, url, bytes` |
| `stage.completed` / `stage.failed` | `stage, summary, duration_seconds, artifact_count` / `error` |
| `run.completed` / `run.failed` | `report_url, duration_seconds, chart_count` / `stage, error, cancelled` |
| `heartbeat` | `elapsed_seconds, active_stage` — every 10s, so silence is visibly *healthy* |

### The `on_event` hook

Each agent entrypoint accepts an optional `on_event` callback. It defaults to
`None`, which is a no-op — so `pipeline.py`, the `__main__` blocks and
`workflow.ipynb` all behave exactly as before:

```python
def run_univariate_analysis(cleaned_csv_path, ..., on_event=None): ...
def run_multivariate_analysis(cleaned_csv_path, ..., on_event=None): ...
def run_data_prep(dataset_path, ..., on_event=None): ...
def run_report(context, ..., on_event=None): ...
```

The hook receives short `(name, payload)` pairs — `progress`, `profile`,
`reasoning`, `turn_completed`, `plan`, `code`, `retry`, `artifact`, `summary`. The
server's orchestrator maps those onto wire event types; the agents themselves stay
unaware of the envelope. Without this hook a stage would emit nothing for 30–240
seconds and the UI would look hung.

### Replay mode

A live run costs 4–12 minutes and real API spend, which makes it a poor loop for
UI work. Every run's events are written to `outputs/runs/{run_id}/events.jsonl`, so
a completed run can be re-streamed with compressed timings and **zero OpenAI
calls** — pick one from the *Replay a past run* dropdown, or:

```bash
curl -X POST http://127.0.0.1:8000/api/runs \
  -H 'Content-Type: application/json' \
  -d '{"mode":"replay","source_run_id":"20260728-142530-a1b2c3"}'
```

Artifact URLs are re-pointed at the source run, so a replay renders the real charts
and the real report.

### Observability design

The pipeline is silent for long stretches — the multivariate stage can spend four
minutes inside one LLM call — so the UI is built around making that legible:

- **Elapsed timers tick client-side**, never waiting on a server event, so
  something always moves.
- **Progress is measured against observed durations** and switches to an
  indeterminate bar past expectation rather than claiming 99% forever.
- **The current sub-step is always on screen** ("Turn 2/2: generating matplotlib
  code", "Executing generated code in a subprocess…").
- **"Last event 34s ago"**, kept small by heartbeats, distinguishes healthy silence
  from a dead connection.
- **Retries are the headline.** A self-correcting agent is the most interesting
  thing that can happen in a run, so `agent.retry` renders as an amber banner
  explaining that the traceback was fed back to the model — a feature, not an error.
- **Skipped plan rows stay visible.** The multivariate agent evaluates ~37 pairs
  and selects 8; its reasons for rejecting the rest are often the best output in
  the run (it rejects `Order ID vs Month` at r=+0.993 as a row-ordering artefact).
  The table flags rows where `meets_threshold` disagrees with `selected` — exactly
  where the agent exercised judgement.

### Limits and caveats

- **Concurrency** is capped at 2 runs (`AGENTIC_EDA_MAX_CONCURRENT_RUNS`); a third
  gets `429`. Each run is minutes of paid compute.
- **Cancellation is cooperative only.** A blocking `client.responses.parse` or
  `subprocess.run` cannot be interrupted, so the flag is checked *between* stages —
  the stage currently executing runs to completion.
- **Closing the browser does not stop a run.** Work happens in a thread pool, not
  in the request task. That is deliberate; reattach later and the snapshot plus
  event log bring you back up to date.
- **Run state is in memory**, mirrored to `run.json` and `events.jsonl`. After a
  restart, completed runs remain inspectable and replayable; runs that were
  in-flight are reported as failed.

### Configuration

All optional, via environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `AGENTIC_EDA_MAX_UPLOAD_MB` | `200` | Upload size cap |
| `AGENTIC_EDA_MAX_CONCURRENT_RUNS` | `2` | Thread-pool size and the `429` threshold |
| `AGENTIC_EDA_HEARTBEAT_SECONDS` | `10` | SSE keepalive interval |
| `AGENTIC_EDA_MAX_BUFFERED_EVENTS` | `2000` | In-memory replay buffer per run |
| `AGENTIC_EDA_REPLAY_SPEED` | `60` | Replay time-compression factor |
| `AGENTIC_EDA_CORS_ORIGINS` | `localhost:5173` | Comma-separated allowed origins |

---

## Manual verification

Nothing here runs automatically — these are the checks to work through by hand.

**Backend protocol (no OpenAI calls, a few seconds):**
```bash
uv run python -m agentic_eda.server.smoke_test
```
Covers upload validation, SSE framing, `seq` monotonicity, `Last-Event-ID` resume,
the snapshot projection, the report endpoint and the artifact mount.

**Frontend typecheck and build:**
```powershell
cd agentic_eda\web ; pnpm build ; pnpm lint
```

**A real live run** (needs `OPENAI_API_KEY`, ~4–12 min, real spend):
1. Upload `agentic_eda/data/sales_data.csv` and confirm the profile shows
   `185950 rows x 11 columns`.
2. Press **Start EDA run**. Watch all four stages transition, reasoning steps
   append live, and the plan tables fill in (11 univariate rows / ~37 multivariate).
3. Confirm 9 + 8 PNGs appear in the galleries as they are created.
4. Confirm the final report renders **with images visible** — that proves the
   relative→absolute image URL transform.
5. Close the tab mid-run, reopen it: the run should still be going (or finished),
   rehydrated from the snapshot.
6. Toggle DevTools offline and back on mid-run: reasoning steps and chart tiles
   must **not** duplicate after the `Last-Event-ID` replay.
7. Start two runs against different datasets, then a third → expect `429`. Confirm
   each `outputs/runs/{id}/charts/` holds only its own PNGs.
8. Replay a completed run and confirm zero OpenAI network activity.

**No CLI/notebook regression:**
```bash
python -m agentic_eda.pipeline
```
should still write to the flat `outputs/{cleaned,charts,reports}` paths, and
`workflow.ipynb` should run unchanged — the `on_event` parameter defaults to a
no-op.

---

## Design Decisions (Brief)

- **Structured Outputs & Pydantic**: Every agent response is strongly validated against a Pydantic schema for reliable behavior.
- **Subprocess Isolation**: Generated Python code is executed in isolated child processes with timeout boundaries for safety.
- **Profile-First Grounding**: Agents are fed real dataset metadata (data profile & correlations) instead of relying on LLM guesses.
- **Multi-Turn Planning**: Analysis agents split work into separate SELECTION (planning) and CODE-GEN (generation) turns for auditable execution.
- **Server-Side Context Continuity**: Chained calls use OpenAI's `store=True` and `previous_response_id` to carry forward conversation context.
- **Self-Correction & Error Isolation**: Code execution tracebacks are fed back to agents for bounded self-healing. Each chart generation block is wrapped in a `try/except` to ensure one error does not fail the entire run.
- **Deterministic Presentation & Multimodal Synthesis**: Presentation layout and Markdown structure are handled deterministically by Python. The report agent uses visual readings of the generated charts to write narrative insights.
- **Non-Invasive Observability**: Agents expose progress through an optional `on_event` hook that defaults to a no-op, so the web server gets per-turn and per-retry visibility without the CLI or notebook changing behaviour. The agents never learn about the wire protocol — the orchestrator owns that translation.
- **Resumable Event Streaming**: Events carry a monotonic `seq` that doubles as the SSE frame `id`, so browser `EventSource` reconnection and `Last-Event-ID` replay come for free. The client drops any `seq` it has already applied, making double delivery — from a reconnect or a second tab — harmless.
- **Runs Outlive Their Viewers**: Blocking agents execute in a thread pool that pushes events onto the event loop via `call_soon_threadsafe`, rather than inside a request handler. A closed tab therefore cannot cancel work that costs minutes and real API spend.
- **Per-Run Artifact Isolation**: Each web run writes to `outputs/runs/{run_id}/`, passed explicitly as `charts_dir` / `output_csv_path` / `output_path`. This is a correctness requirement, not tidiness: the chart executor discovers its PNGs by mtime globbing, so a shared directory lets concurrent runs steal each other's output.
- **Durable Event Log & Free Replay**: Every event is appended to `events.jsonl`, which serves three purposes at once — crash recovery, post-restart inspection, and a replay mode that re-streams a finished run with no OpenAI calls.
