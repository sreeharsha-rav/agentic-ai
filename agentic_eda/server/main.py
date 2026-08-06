"""FastAPI application for the Agentic EDA pipeline.

Run it with::

    uv run uvicorn agentic_eda.server.main:app --reload --port 8000

The `--reload` flag is safe here: worker threads and their `subprocess` children
live inside the reloaded worker process, so a reload leaves no orphans. It does
abandon any in-flight run's in-memory state, though the run's `events.jsonl`
survives and can be replayed.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
import sys

# Ensure workspace root containing `agentic_eda` package is in sys.path
_workspace_root = Path(__file__).resolve().parents[2]
if str(_workspace_root) not in sys.path:
    sys.path.insert(0, str(_workspace_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from agentic_eda.config import OPENAI_API_KEY, RUNS_DIR


from agentic_eda.server.api import datasets, runs
from agentic_eda.server.models.events import (
    STAGE_EXPECTED_SECONDS,
    STAGE_LABELS,
    STAGE_ORDER,
    EventType,
)
from agentic_eda.server.services.run_manager import run_manager
from agentic_eda.server.services.storage import ARTIFACTS_URL_PREFIX
from agentic_eda.server.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Bind the run manager to this process's event loop, and tear it down."""
    run_manager.bind_loop(asyncio.get_running_loop())

    if not OPENAI_API_KEY:
        logger.warning(
            "OPENAI_API_KEY is not set. Uploads and replay will work, but live "
            "runs will fail at the first agent. Add it to agentic_eda/.env"
        )
    logger.info(
        "Agentic EDA server ready (max %d concurrent run(s), artifacts at %s)",
        settings.max_concurrent_runs,
        ARTIFACTS_URL_PREFIX,
    )

    try:
        yield
    finally:
        run_manager.shutdown()
        logger.info("Agentic EDA server shut down")


app = FastAPI(
    title="Agentic EDA",
    description=(
        "Upload a CSV, trigger the four-agent exploratory data analysis pipeline, "
        "and stream every agent's reasoning, generated code, charts and report "
        "as Server-Sent Events."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# The Vite dev server proxies /api and /artifacts, so CORS is only a fallback for
# running the two dev servers without that proxy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Location"],
)

app.include_router(datasets.router)
app.include_router(runs.router)

# Charts, cleaned CSVs and reports are written under RUNS_DIR by the agents.
# Serving that tree directly means the report's own relative image links
# (`../charts/univariate/sales.png`) resolve correctly for anything that fetches
# the markdown file by URL.
RUNS_DIR.mkdir(parents=True, exist_ok=True)
app.mount(
    ARTIFACTS_URL_PREFIX,
    StaticFiles(directory=RUNS_DIR),
    name="artifacts",
)


@app.get("/api/health", tags=["meta"])
async def health() -> dict:
    """Liveness plus the bits of config a client needs to render sensibly."""
    return {
        "status": "ok",
        "openai_key_configured": bool(OPENAI_API_KEY),
        "max_concurrent_runs": settings.max_concurrent_runs,
        "active_runs": run_manager.active_count,
        "artifacts_url_prefix": ARTIFACTS_URL_PREFIX,
        "heartbeat_seconds": settings.heartbeat_seconds,
    }


@app.get("/api/meta/stages", tags=["meta"])
async def stage_metadata() -> dict:
    """Stage order, labels and expected durations.

    Lets the client render the full four-stage timeline before a run starts, and
    draw honest progress bars against real observed timings.
    """
    return {
        "stages": [
            {
                "id": stage.value,
                "label": STAGE_LABELS[stage],
                "expected_seconds": STAGE_EXPECTED_SECONDS[stage],
            }
            for stage in STAGE_ORDER
        ],
        "event_types": [event_type.value for event_type in EventType],
    }
