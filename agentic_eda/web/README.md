# Agentic EDA — Web Client

React + TypeScript + Vite dashboard for the Agentic EDA pipeline. It streams a
four-agent run over Server-Sent Events and renders each agent's reasoning,
generated code, per-variable decisions, charts and the final report as they arrive.

Full setup, endpoint reference and event protocol live in
[../README.md](../README.md#web-application).

## Commands

```powershell
pnpm install     # once
pnpm dev         # dev server on :5173, proxies /api and /artifacts to :8000
pnpm build       # typecheck (tsc -b) + production bundle into dist/
pnpm lint        # oxlint
```

The backend must be running separately:

```powershell
# from the repository root
uv run uvicorn agentic_eda.server.main:app --reload --port 8000
```

Point the proxy elsewhere with `AGENTIC_EDA_API=http://host:port pnpm dev`.

## Layout

```
src/
├── types/events.ts       Discriminated union mirroring server/models/events.py
├── api/
│   ├── client.ts         REST calls (upload uses XHR for progress events)
│   └── eventStream.ts    EventSource wrapper — reconnect + Last-Event-ID
├── state/runReducer.ts   Projected run state; drops any seq already applied
├── hooks/
│   ├── useEdaRun.ts      Trigger, subscribe, rehydrate, cancel
│   └── useElapsed.ts     Local ticking clocks (never wait on server events)
├── components/           Timeline, stage cards, plan tables, gallery, report
└── styles/               tokens.css (light + dark), global.css
```

## Two things worth knowing before editing

**Runs are created in click handlers, never in effects.** React StrictMode runs
effect bodies twice in development. Creating a run there would fire two paid 4–12
minute pipelines per click. Subscribing *is* done in an effect, which is safe
because it is read-only and the reducer discards replayed events by `seq`.

**The reducer is the source of truth, not the event array.** Events are folded into
a normalized `stages` map; the raw log is a capped ring buffer feeding the debug
drawer only. Keeping the raw array as state would re-render the tree on every one of
several hundred events.
