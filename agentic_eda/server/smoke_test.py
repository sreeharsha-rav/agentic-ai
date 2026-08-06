"""Manual smoke test for the server. Run it yourself; nothing runs this for you.

    uv run python -m agentic_eda.server.smoke_test

Exercises upload validation, the SSE protocol, `Last-Event-ID` resume, the
snapshot projection and the artifact mount using a synthetic recorded run — so it
makes **no OpenAI calls** and costs nothing. It does not need a server to be
running; it drives the ASGI app in-process.

What it deliberately does NOT cover, because that needs real API spend and 4-12
minutes: a genuine live run end to end. See the "Manual verification" section of
agentic_eda/README.md for that checklist.
"""

import json
from pathlib import Path
import shutil
import sys

# Ensure workspace root containing `agentic_eda` package is in sys.path
_workspace_root = Path(__file__).resolve().parents[2]
if str(_workspace_root) not in sys.path:
    sys.path.insert(0, str(_workspace_root))

from agentic_eda.config import RUNS_DIR
from agentic_eda.server.main import app

from agentic_eda.server.models.events import EventEnvelope, EventType, StageId
from agentic_eda.server.services import storage

FAKE_RUN_ID = "19990101-000000-smoke"

CSV = (
    "Order ID,Product,Quantity Ordered,Price Each,Order Date,City\n"
    "1,USB-C Cable,2,11.95,2019-12-30 00:01:00,New York City\n"
    "2,Macbook Pro,1,1700.00,2019-12-29 07:03:00,San Francisco\n"
    "3,AA Batteries,4,3.84,2019-12-12 18:21:00,Dallas\n"
    "4,27in Monitor,1,149.99,2019-12-22 15:13:00,Atlanta\n"
    "5,LG Dryer,1,600.00,2019-12-18 12:38:00,Portland\n"
)

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label} {detail}")
        failures.append(label)


def seed_recorded_run() -> None:
    """Write a synthetic events.jsonl so replay has something to stream."""
    paths = storage.create_run_paths(FAKE_RUN_ID)
    events: list[EventEnvelope] = []
    seq = 0

    def add(event_type, payload, stage=None):
        nonlocal seq
        seq += 1
        events.append(
            EventEnvelope(
                seq=seq,
                run_id=FAKE_RUN_ID,
                type=event_type,
                stage=stage,
                payload=payload,
            )
        )

    add(
        EventType.RUN_STARTED,
        {
            "run_id": FAKE_RUN_ID,
            "dataset_name": "smoke_data",
            "mode": "live",
            "stages": [
                {"id": s.value, "label": s.value, "expected_seconds": 10} for s in StageId
            ],
        },
    )
    add(
        EventType.STAGE_STARTED,
        {"stage": "data_prep", "label": "Data Preparation", "expected_seconds": 50},
        StageId.DATA_PREP,
    )
    add(EventType.STAGE_PROGRESS, {"message": "profiling raw dataset"}, StageId.DATA_PREP)
    add(
        EventType.AGENT_REASONING,
        {
            "index": 0,
            "phase": "load",
            "observation": "5 rows, 6 columns",
            "action": "read the CSV",
        },
        StageId.DATA_PREP,
    )
    add(
        EventType.AGENT_CODE,
        {"language": "python", "code": "import pandas as pd\ndf = pd.read_csv(DATASET_PATH)"},
        StageId.DATA_PREP,
    )
    add(
        EventType.STAGE_COMPLETED,
        {
            "stage": "data_prep",
            "summary": "Cleaned.",
            "duration_seconds": 41.2,
            "artifact_count": 1,
        },
        StageId.DATA_PREP,
    )
    add(
        EventType.STAGE_STARTED,
        {"stage": "univariate", "label": "Univariate Analysis", "expected_seconds": 105},
        StageId.UNIVARIATE,
    )
    add(
        EventType.AGENT_PLAN,
        {
            "kind": "variable",
            "items": [
                {
                    "variable": "Sales",
                    "data_kind": "numeric_continuous",
                    "chart_type": "histogram",
                    "selected": True,
                    "rationale": "distribution",
                    "output_filename": "sales.png",
                }
            ],
        },
        StageId.UNIVARIATE,
    )
    add(
        EventType.AGENT_RETRY,
        {"attempt": 1, "max_attempts": 2, "error": "ValueError: boom"},
        StageId.UNIVARIATE,
    )
    add(
        EventType.STAGE_COMPLETED,
        {
            "stage": "univariate",
            "summary": "9 charts.",
            "duration_seconds": 98.0,
            "artifact_count": 9,
        },
        StageId.UNIVARIATE,
    )
    add(
        EventType.RUN_COMPLETED,
        {
            "report_url": f"/artifacts/{FAKE_RUN_ID}/reports/r.md",
            "duration_seconds": 300.0,
            "chart_count": 17,
        },
    )

    with paths.events_path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(event.model_dump_json() + "\n")

    (paths.reports_dir / "smoke_data_eda_report.md").write_text(
        "# Report\n\n![sales](../charts/univariate/sales.png)\n", encoding="utf-8"
    )
    print(f"  seeded {len(events)} recorded events for {FAKE_RUN_ID}")


def parse_sse(raw: str) -> list[dict]:
    """Parse an SSE body into event dicts."""
    parsed = []
    for block in raw.split("\n\n"):
        block = block.strip()
        if not block or block.startswith(":"):
            continue
        record: dict = {}
        for line in block.splitlines():
            if line.startswith("id:"):
                record["id"] = line[3:].strip()
            elif line.startswith("event:"):
                record["event"] = line[6:].strip()
            elif line.startswith("data:"):
                record["data"] = json.loads(line[5:].strip())
        if "event" in record:
            parsed.append(record)
    return parsed


def main() -> None:
    from fastapi.testclient import TestClient

    seed_recorded_run()

    with TestClient(app) as client:
        print("\n[1] health + stage metadata")
        health = client.get("/api/health")
        check("health 200", health.status_code == 200, health.text)
        check(
            "health reports artifact prefix",
            health.json().get("artifacts_url_prefix") == "/artifacts",
        )
        stages = client.get("/api/meta/stages").json()
        check("4 stages advertised", len(stages["stages"]) == 4, str(stages))
        check("event types advertised", "agent.retry" in stages["event_types"])

        print("\n[2] upload validation")
        bad = client.post(
            "/api/datasets", files={"file": ("notes.txt", b"hello", "text/plain")}
        )
        check("non-csv rejected 400", bad.status_code == 400, bad.text)
        empty = client.post("/api/datasets", files={"file": ("empty.csv", b"", "text/csv")})
        check("empty csv rejected", empty.status_code in (400, 422), empty.text)

        print("\n[3] upload a real csv")
        upload = client.post(
            "/api/datasets", files={"file": ("smoke_data.csv", CSV.encode(), "text/csv")}
        )
        check("upload 201", upload.status_code == 201, upload.text)
        info = upload.json()
        dataset_id = info["dataset_id"]
        check("profile contains shape", "Shape:" in info["profile"])
        check("rows parsed from profile", info["rows"] == 5, str(info.get("rows")))
        check("columns parsed from profile", info["columns"] == 6, str(info.get("columns")))
        listing = client.get("/api/datasets").json()
        check(
            "dataset appears in listing",
            any(d["dataset_id"] == dataset_id for d in listing),
        )

        print("\n[4] run creation error paths")
        check(
            "unknown dataset 404",
            client.post("/api/runs", json={"dataset_id": "nope"}).status_code == 404,
        )
        check("missing dataset_id 400", client.post("/api/runs", json={}).status_code == 400)
        check(
            "replay without source 400",
            client.post("/api/runs", json={"mode": "replay"}).status_code == 400,
        )
        check(
            "replay unknown source 404",
            client.post(
                "/api/runs", json={"mode": "replay", "source_run_id": "nope"}
            ).status_code
            == 404,
        )
        check("unknown run 404", client.get("/api/runs/nope").status_code == 404)

        print("\n[5] replay run + SSE stream")
        created = client.post(
            "/api/runs", json={"mode": "replay", "source_run_id": FAKE_RUN_ID}
        )
        check("replay accepted 202", created.status_code == 202, created.text)
        run_id = created.json()["run_id"]
        check(
            "Location header set",
            created.headers.get("Location") == f"/api/runs/{run_id}/events",
        )

        with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
            check("stream 200", stream.status_code == 200)
            check(
                "content-type is event-stream",
                "text/event-stream" in stream.headers.get("content-type", ""),
            )
            raw = "".join(chunk for chunk in stream.iter_text())

        events = parse_sse(raw)
        real = [e for e in events if e["event"] != "heartbeat"]
        types = [e["event"] for e in real]

        check("received events", len(real) >= 11, f"got {len(real)}")
        check("starts with run.started", types[0] == "run.started", str(types[:3]))
        check("ends with run.completed", types[-1] == "run.completed", str(types[-3:]))
        check("retry event present", "agent.retry" in types)
        check("plan event present", "agent.plan" in types)
        check("code event present", "agent.code" in types)
        check("advertises reconnect interval", "retry: 3000" in raw)

        seqs = [e["data"]["seq"] for e in real]
        check("seq strictly increasing", seqs == sorted(set(seqs)), str(seqs))
        check("sse id matches seq", all(int(e["id"]) == e["data"]["seq"] for e in real))
        check(
            "replay run_id stamped on events",
            all(e["data"]["run_id"] == run_id for e in real),
        )
        completed = [e for e in real if e["event"] == "run.completed"]
        check(
            "report_url repointed at source run",
            bool(completed) and FAKE_RUN_ID in completed[0]["data"]["payload"]["report_url"],
        )

        print("\n[6] Last-Event-ID resume")
        resume_from = seqs[len(seqs) // 2]
        with client.stream(
            "GET",
            f"/api/runs/{run_id}/events",
            headers={"Last-Event-ID": str(resume_from)},
        ) as stream:
            raw2 = "".join(chunk for chunk in stream.iter_text())
        resumed = [e["data"]["seq"] for e in parse_sse(raw2) if e["event"] != "heartbeat"]
        check("resume skips seen events", all(s > resume_from for s in resumed), str(resumed))
        check(
            "resume replays the remainder",
            resumed == [s for s in seqs if s > resume_from],
            str(resumed),
        )

        print("\n[7] snapshot projection")
        snap = client.get(f"/api/runs/{run_id}").json()
        check("snapshot completed", snap["status"] == "completed", snap["status"])
        check("snapshot has 4 stages", len(snap["stages"]) == 4)
        prep = snap["stages"]["data_prep"]
        check("data_prep completed", prep["status"] == "completed")
        check("data_prep reasoning captured", len(prep["reasoning"]) == 1)
        check("data_prep code captured", prep["code"] is not None)
        check("data_prep summary captured", prep["summary"] == "Cleaned.")
        uni = snap["stages"]["univariate"]
        check("univariate retry captured", len(uni["retries"]) == 1)
        check("univariate plan captured", uni["plan_kind"] == "variable")
        check("multivariate still pending", snap["stages"]["multivariate"]["status"] == "pending")
        check("last_seq tracked", snap["last_seq"] == max(seqs))

        print("\n[8] report endpoint + artifact mount")
        report = client.get(f"/api/runs/{run_id}/report")
        check("report 200", report.status_code == 200, report.text[:200])
        check(
            "base_url points at source reports dir",
            report.json()["base_url"] == f"/artifacts/{FAKE_RUN_ID}/reports/",
        )
        served = client.get(f"/artifacts/{FAKE_RUN_ID}/reports/smoke_data_eda_report.md")
        check("artifact served 200", served.status_code == 200)
        check(
            "missing artifact 404",
            client.get(f"/artifacts/{FAKE_RUN_ID}/charts/univariate/nope.png").status_code
            == 404,
        )

        storage.discard_upload(dataset_id)

    shutil.rmtree(RUNS_DIR / FAKE_RUN_ID, ignore_errors=True)

    print("\n" + "=" * 60)
    if failures:
        print(f"{len(failures)} CHECK(S) FAILED:")
        for name in failures:
            print(f"  - {name}")
        raise SystemExit(1)
    print("ALL SERVER SMOKE CHECKS PASSED")


if __name__ == "__main__":
    main()
