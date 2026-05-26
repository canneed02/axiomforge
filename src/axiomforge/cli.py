from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .kernel import counts, create_task, initialize, paths, publish_lab_note, register_artifact, run_bootstrap_cycle


def default_root() -> Path:
    return Path(os.getenv("AXIOMFORGE_ROOT", "./state"))


def main() -> None:
    parser = argparse.ArgumentParser(prog="axiomforge")
    parser.add_argument("--root", type=Path, default=default_root())
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Initialize AxiomForge state.")

    subparsers.add_parser("status", help="Print registry counts.")

    cycle = subparsers.add_parser("cycle", help="Run one Phase 0 bootstrap cycle.")
    cycle.add_argument("--goal", required=True)

    task = subparsers.add_parser("create-task", help="Create a research task.")
    task.add_argument("--title", required=True)
    task.add_argument("--kind", default="research")

    artifact = subparsers.add_parser("register-artifact", help="Register an artifact path.")
    artifact.add_argument("--path", type=Path, required=True)
    artifact.add_argument("--kind", required=True)
    artifact.add_argument("--description", required=True)

    note = subparsers.add_parser("publish-note", help="Publish a local autonomous lab note.")
    note.add_argument("--title", required=True)
    note.add_argument("--claim-type", required=True)
    note.add_argument("--evidence", required=True)
    note.add_argument("--body", required=True)

    args = parser.parse_args()
    root = args.root

    if args.command == "init":
        p = initialize(root)
        print(f"initialized={p.root}")
        return

    if args.command == "status":
        p = initialize(root)
        print(json.dumps(counts(p), sort_keys=True))
        return

    if args.command == "cycle":
        out = run_bootstrap_cycle(root, args.goal)
        print(f"lab_note={out}")
        return

    if args.command == "create-task":
        p = initialize(root)
        task_id = create_task(p, args.title, args.kind)
        print(f"task={task_id}")
        return

    if args.command == "register-artifact":
        p = initialize(root)
        artifact_id = register_artifact(p, args.path, args.kind, args.description)
        print(f"artifact={artifact_id}")
        return

    if args.command == "publish-note":
        p = initialize(root)
        out = publish_lab_note(
            p,
            title=args.title,
            claim_type=args.claim_type,
            body=args.body,
            evidence=args.evidence,
        )
        print(f"lab_note={out}")
        return

    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
