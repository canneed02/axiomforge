from __future__ import annotations

import json
import re
import sqlite3
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


def initialize(root: Path) -> ForgePaths:
    p = paths(root)
    p.root.mkdir(parents=True, exist_ok=True)
    p.artifacts.mkdir(parents=True, exist_ok=True)
    p.public.mkdir(parents=True, exist_ok=True)
    p.lab_notes.mkdir(parents=True, exist_ok=True)
    if not p.events.exists():
        p.events.write_text("")
    with sqlite3.connect(p.db) as db:
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
    with sqlite3.connect(p.db) as db:
        db.execute(
            "INSERT INTO events (ts, kind, payload_json) VALUES (?, ?, ?)",
            (record["ts"], kind, json.dumps(payload, sort_keys=True)),
        )


def create_task(p: ForgePaths, title: str, kind: str, payload: dict[str, Any] | None = None) -> int:
    payload = payload or {}
    ts = utc_now()
    with sqlite3.connect(p.db) as db:
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
    with sqlite3.connect(p.db) as db:
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
    with sqlite3.connect(p.db) as db:
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
    with sqlite3.connect(p.db) as db:
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
    with sqlite3.connect(p.db) as db:
        return {
            table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ["events", "tasks", "claims", "artifacts", "publications"]
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
