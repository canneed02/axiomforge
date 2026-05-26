from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .policy import validate_claim_type, validate_lab_note


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ForgePaths:
    root: Path
    db: Path
    events: Path
    artifacts: Path
    public: Path
    lab_notes: Path


@dataclass(frozen=True)
class PublicationQueueItem:
    id: int
    title: str
    path: Path
    target: str
    status: str
    policy: dict[str, Any]


def paths(root: Path) -> ForgePaths:
    root = root.expanduser().resolve()
    return ForgePaths(
        root=root,
        db=root / "axiomforge.db",
        events=root / "events.jsonl",
        artifacts=root / "artifacts",
        public=root / "public",
        lab_notes=root / "public" / "lab-notes",
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "untitled"


@contextmanager
def db_session(p: ForgePaths):
    db = sqlite3.connect(p.db)
    try:
        yield db
        db.commit()
    finally:
        db.close()


def initialize(root: Path) -> ForgePaths:
    p = paths(root)
    p.root.mkdir(parents=True, exist_ok=True)
    p.artifacts.mkdir(parents=True, exist_ok=True)
    p.public.mkdir(parents=True, exist_ok=True)
    p.lab_notes.mkdir(parents=True, exist_ok=True)
    if not p.events.exists():
        p.events.write_text("")
    with db_session(p) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                title TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                claim_type TEXT NOT NULL,
                statement TEXT NOT NULL,
                evidence TEXT NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                path TEXT NOT NULL,
                kind TEXT NOT NULL,
                description TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS publications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                title TEXT NOT NULL,
                claim_type TEXT NOT NULL,
                path TEXT NOT NULL,
                evidence TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS research_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                goal TEXT NOT NULL,
                program TEXT NOT NULL,
                status TEXT NOT NULL,
                proposal_json TEXT NOT NULL,
                verifier_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS publication_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                title TEXT NOT NULL,
                path TEXT NOT NULL,
                target TEXT NOT NULL,
                status TEXT NOT NULL,
                policy_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS code_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                objective TEXT NOT NULL,
                workspace TEXT NOT NULL,
                status TEXT NOT NULL,
                summary_json TEXT NOT NULL
            );
            """
        )
        db.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
    append_event(p, "kernel.initialized", {"schema_version": SCHEMA_VERSION})
    return p


def append_event(p: ForgePaths, kind: str, payload: dict[str, Any]) -> None:
    record = {"ts": utc_now(), "kind": kind, "payload": payload}
    with p.events.open("a") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    with db_session(p) as db:
        db.execute(
            "INSERT INTO events (ts, kind, payload_json) VALUES (?, ?, ?)",
            (record["ts"], kind, json.dumps(payload, sort_keys=True)),
        )


def create_task(p: ForgePaths, title: str, kind: str, payload: dict[str, Any] | None = None) -> int:
    payload = payload or {}
    ts = utc_now()
    with db_session(p) as db:
        cursor = db.execute(
            """
            INSERT INTO tasks (ts, title, kind, status, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ts, title, kind, "open", json.dumps(payload, sort_keys=True)),
        )
        task_id = int(cursor.lastrowid)
    append_event(p, "task.created", {"id": task_id, "title": title, "kind": kind})
    return task_id


def register_claim(p: ForgePaths, claim_type: str, statement: str, evidence: str, status: str = "open") -> int:
    gate = validate_claim_type(claim_type)
    if not gate.ok:
        raise ValueError("; ".join(gate.reasons))
    ts = utc_now()
    with db_session(p) as db:
        cursor = db.execute(
            """
            INSERT INTO claims (ts, claim_type, statement, evidence, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ts, claim_type, statement, evidence, status),
        )
        claim_id = int(cursor.lastrowid)
    append_event(p, "claim.registered", {"id": claim_id, "claim_type": claim_type, "evidence": evidence})
    return claim_id


def register_artifact(p: ForgePaths, path: Path, kind: str, description: str) -> int:
    ts = utc_now()
    artifact_path = str(path)
    with db_session(p) as db:
        cursor = db.execute(
            """
            INSERT INTO artifacts (ts, path, kind, description)
            VALUES (?, ?, ?, ?)
            """,
            (ts, artifact_path, kind, description),
        )
        artifact_id = int(cursor.lastrowid)
    append_event(p, "artifact.registered", {"id": artifact_id, "path": artifact_path, "kind": kind})
    return artifact_id


def register_research_run(
    p: ForgePaths,
    *,
    goal: str,
    program: str,
    status: str,
    proposal: dict[str, Any],
    verifier: dict[str, Any],
) -> int:
    ts = utc_now()
    with db_session(p) as db:
        cursor = db.execute(
            """
            INSERT INTO research_runs (ts, goal, program, status, proposal_json, verifier_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                ts,
                goal,
                program,
                status,
                json.dumps(proposal, sort_keys=True),
                json.dumps(verifier, sort_keys=True),
            ),
        )
        run_id = int(cursor.lastrowid)
    append_event(p, "research_run.registered", {"id": run_id, "goal": goal, "program": program, "status": status})
    return run_id


def enqueue_publication(
    p: ForgePaths,
    *,
    title: str,
    path: Path,
    target: str,
    status: str,
    policy: dict[str, Any],
) -> int:
    ts = utc_now()
    publication_path = str(path)
    with db_session(p) as db:
        cursor = db.execute(
            """
            INSERT INTO publication_queue (ts, title, path, target, status, policy_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ts, title, publication_path, target, status, json.dumps(policy, sort_keys=True)),
        )
        queue_id = int(cursor.lastrowid)
    append_event(
        p,
        "publication.queued",
        {"id": queue_id, "title": title, "path": publication_path, "target": target, "status": status},
    )
    return queue_id


def register_code_run(
    p: ForgePaths,
    *,
    objective: str,
    workspace: Path,
    status: str,
    summary: dict[str, Any],
) -> int:
    ts = utc_now()
    with sqlite3.connect(p.db) as db:
        cursor = db.execute(
            """
            INSERT INTO code_runs (ts, objective, workspace, status, summary_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ts, objective, str(workspace), status, json.dumps(summary, sort_keys=True)),
        )
        run_id = int(cursor.lastrowid)
    append_event(p, "code_run.registered", {"id": run_id, "objective": objective, "status": status})
    return run_id


def queued_publications(p: ForgePaths, status: str = "ready") -> list[PublicationQueueItem]:
    with db_session(p) as db:
        rows = db.execute(
            """
            SELECT id, title, path, target, status, policy_json
            FROM publication_queue
            WHERE status = ?
            ORDER BY id
            """,
            (status,),
        ).fetchall()
    return [
        PublicationQueueItem(
            id=int(row[0]),
            title=str(row[1]),
            path=Path(str(row[2])),
            target=str(row[3]),
            status=str(row[4]),
            policy=json.loads(str(row[5])),
        )
        for row in rows
    ]


def update_publication_status(p: ForgePaths, queue_id: int, status: str, detail: dict[str, Any]) -> None:
    with db_session(p) as db:
        row = db.execute(
            "SELECT policy_json FROM publication_queue WHERE id = ?",
            (queue_id,),
        ).fetchone()
        policy = json.loads(str(row[0])) if row else {}
        policy["status_detail"] = detail
        db.execute(
            """
            UPDATE publication_queue SET status = ?, policy_json = ? WHERE id = ?
            """,
            (status, json.dumps(policy, sort_keys=True), queue_id),
        )
    append_event(p, "publication.status", {"id": queue_id, "status": status, "detail": detail})


def publish_lab_note(p: ForgePaths, *, title: str, claim_type: str, body: str, evidence: str) -> Path:
    gate = validate_lab_note(title=title, claim_type=claim_type, body=body, evidence=evidence)
    if not gate.ok:
        raise ValueError("; ".join(gate.reasons))
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S-%f")
    out = p.lab_notes / f"{stamp}-{slugify(title)}.md"
    note = f"""# {title}

This note was generated by the AxiomForge autonomous research system.

Claim type: `{claim_type}`

Evidence:

```text
{evidence}
```

{body.strip()}
"""
    out.write_text(note + "\n")
    register_artifact(p, out, "lab_note", title)
    with db_session(p) as db:
        db.execute(
            """
            INSERT INTO publications (ts, title, claim_type, path, evidence)
            VALUES (?, ?, ?, ?, ?)
            """,
            (utc_now(), title, claim_type, str(out), evidence),
        )
    append_event(p, "publication.lab_note", {"title": title, "claim_type": claim_type, "path": str(out)})
    return out


def counts(p: ForgePaths) -> dict[str, int]:
    with db_session(p) as db:
        return {
            table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in [
                "events",
                "tasks",
                "claims",
                "artifacts",
                "publications",
                "research_runs",
                "publication_queue",
                "code_runs",
            ]
        }


def run_bootstrap_cycle(root: Path, goal: str) -> Path:
    p = initialize(root)
    task_id = create_task(
        p,
        title=f"Bootstrap cycle: {goal}",
        kind="bootstrap",
        payload={"goal": goal},
    )
    evidence = f"events={p.events}; task_id={task_id}"
    register_claim(
        p,
        "measured",
        "AxiomForge Phase 0 kernel can create durable event, task, claim, artifact, and publication records.",
        evidence,
        status="measured",
    )
    body = """
## Observation

The autonomous system initialized its kernel state, created a task, registered a
measured claim, and emitted this lab note through the local publication gate.

## Limitations

This is only a Phase 0 bootstrap cycle. It does not include external paper
submission, web publication, theorem proving, code-writing autonomy, or
multi-agent review yet.
"""
    return publish_lab_note(
        p,
        title="Phase 0 Bootstrap Cycle",
        claim_type="measured",
        body=body,
        evidence=evidence,
    )
