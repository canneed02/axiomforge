from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .kernel import counts, create_task, initialize, publish_lab_note, register_artifact, run_bootstrap_cycle
from .providers import nvidia_inventory_from_env
from .proof import run_proof_cycle
from .publisher import DEFAULT_PUBLICATION_BRANCH, publish_ready_queue
from .research import run_phase1_research_cycle
from .review import run_review_cycle
from .sandbox import run_code_cycle
from .site import publish_public_site


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

    research_cycle = subparsers.add_parser("research-cycle", help="Run one Phase 1 autonomous research cycle.")
    research_cycle.add_argument("--goal", required=True)

    code_cycle = subparsers.add_parser("code-cycle", help="Run one Phase 2 sandbox code-writing cycle.")
    code_cycle.add_argument("--objective", required=True)
    code_cycle.add_argument("--timeout-seconds", type=int, default=30)

    proof_cycle = subparsers.add_parser("proof-cycle", help="Run one Phase 3 proof/experiment cycle.")
    proof_cycle.add_argument("--objective", required=True)
    proof_cycle.add_argument("--timeout-seconds", type=int, default=45)

    review_cycle = subparsers.add_parser("review-cycle", help="Run one Phase 4 reviewer/replicator gate cycle.")
    review_cycle.add_argument("--timeout-seconds", type=int, default=45)

    subparsers.add_parser("provider-inventory", help="Print redacted provider inventory.")

    publisher = subparsers.add_parser("publish-ready", help="Publish ready queue items to the autonomous output branch.")
    publisher.add_argument("--repo", type=Path, default=Path(os.getenv("AXIOMFORGE_PUBLICATION_REPO", "./publication-repo")))
    publisher.add_argument("--branch", default=os.getenv("AXIOMFORGE_PUBLICATION_BRANCH", DEFAULT_PUBLICATION_BRANCH))
    publisher.add_argument("--no-push", action="store_true")

    site = subparsers.add_parser("site-build", help="Build and publish the public lab-note site.")
    site.add_argument("--repo", type=Path, default=Path(os.getenv("AXIOMFORGE_PUBLICATION_REPO", "./publication-repo")))
    site.add_argument("--branch", default=os.getenv("AXIOMFORGE_PUBLICATION_BRANCH", DEFAULT_PUBLICATION_BRANCH))
    site.add_argument("--no-push", action="store_true")

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

    if args.command == "research-cycle":
        out = run_phase1_research_cycle(root, args.goal)
        print(f"lab_note={out}")
        return

    if args.command == "code-cycle":
        out = run_code_cycle(root, args.objective, timeout_seconds=args.timeout_seconds)
        print(f"lab_note={out}")
        return

    if args.command == "proof-cycle":
        out = run_proof_cycle(root, args.objective, timeout_seconds=args.timeout_seconds)
        print(f"lab_note={out}")
        return

    if args.command == "review-cycle":
        out = run_review_cycle(root, timeout_seconds=args.timeout_seconds)
        print(f"lab_note={out}")
        return

    if args.command == "provider-inventory":
        print(json.dumps(nvidia_inventory_from_env().public_dict(), sort_keys=True))
        return

    if args.command == "publish-ready":
        results = publish_ready_queue(root, args.repo, branch=args.branch, push=not args.no_push)
        print(json.dumps([result.__dict__ for result in results], sort_keys=True))
        return

    if args.command == "site-build":
        result = publish_public_site(args.repo, branch=args.branch, push=not args.no_push)
        print(json.dumps(result.__dict__, sort_keys=True))
        if result.status != "passed":
            raise SystemExit(1)
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
