"""Server-side tunables.

Kept separate from `agentic_eda.config` (which owns filesystem paths and the
OpenAI key) so the web layer's knobs are all in one place. Every value can be
overridden with an `AGENTIC_EDA_*` environment variable.
"""

import os
from dataclasses import dataclass, field


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class ServerSettings:
    """Configuration for the FastAPI layer."""

    # --- Uploads ---------------------------------------------------------- #
    # Datasets are streamed to disk in chunks; the sample sales CSV is ~22 MB.
    max_upload_bytes: int = field(
        default_factory=lambda: _env_int("AGENTIC_EDA_MAX_UPLOAD_MB", 200) * 1024 * 1024
    )
    upload_chunk_bytes: int = 1024 * 1024
    allowed_upload_suffixes: tuple[str, ...] = (".csv",)

    # --- Run execution ---------------------------------------------------- #
    # Agents are fully blocking (LLM calls + subprocess + multi-second CSV
    # reads), so they run in a thread pool. Each run costs real OpenAI spend and
    # 4-12 minutes, hence a deliberately small cap.
    max_concurrent_runs: int = field(
        default_factory=lambda: _env_int("AGENTIC_EDA_MAX_CONCURRENT_RUNS", 2)
    )

    # --- Streaming -------------------------------------------------------- #
    # A stage can be silent for minutes; heartbeats keep proxies from dropping
    # the connection and feed the client's "last event Ns ago" indicator.
    heartbeat_seconds: float = field(
        default_factory=lambda: _env_float("AGENTIC_EDA_HEARTBEAT_SECONDS", 10.0)
    )
    # Per-run in-memory event history used for Last-Event-ID replay. Generated
    # code and profile strings run to KBs, so this is capped; the full history
    # always remains on disk in events.jsonl.
    max_buffered_events: int = field(
        default_factory=lambda: _env_int("AGENTIC_EDA_MAX_BUFFERED_EVENTS", 2000)
    )
    subscriber_queue_size: int = 1000

    # --- Replay ----------------------------------------------------------- #
    # Replay compresses the real inter-event gaps so a 12-minute run can be
    # reviewed in seconds without any OpenAI calls.
    replay_speed: float = field(
        default_factory=lambda: _env_float("AGENTIC_EDA_REPLAY_SPEED", 60.0)
    )
    replay_max_gap_seconds: float = field(
        default_factory=lambda: _env_float("AGENTIC_EDA_REPLAY_MAX_GAP", 0.75)
    )

    # --- CORS ------------------------------------------------------------- #
    # The Vite dev server proxies /api and /artifacts, so CORS is only a
    # fallback for running the two dev servers without the proxy.
    cors_origins: list[str] = field(
        default_factory=lambda: _env_list(
            "AGENTIC_EDA_CORS_ORIGINS",
            [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ],
        )
    )

    # --- Errors ----------------------------------------------------------- #
    # Subprocess tracebacks fed back to the agents can be long; truncate before
    # putting them on the wire.
    max_error_chars: int = 4000


settings = ServerSettings()
