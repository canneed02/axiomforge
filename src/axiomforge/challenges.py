from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .kernel import (
    create_task,
    db_session,
    enqueue_publication,
    initialize,
    publish_lab_note,
    register_artifact,
    register_challenge_run,
    register_claim,
    slugify,
    update_challenge_run,
    utc_now,
)
from .paper import build_paper_package
from .proof import run_proof_cycle
from .publisher import DEFAULT_PUBLICATION_BRANCH, publish_ready_queue
from .release import build_release_candidate
from .review import run_review_cycle
from .sandbox import run_code_cycle
from .site import publish_public_site


@dataclass(frozen=True)
class ChallengeResult:
    challenge_id: str
    status: str
    manifest: str
    route_status: str
    errors: tuple[str, ...]


GRAND_CHALLENGES: tuple[dict[str, Any], ...] = (
    {
        "id": "verifier_backed_ai_evaluation",
        "title": "Verifier-backed AI evaluation beyond static benchmarks",
        "objective_type": "real_research",
        "central_question": "Can frontier-model evaluations be grounded in executable verifiers rather than prompt-only judgment?",
        "claim_boundary": "Only claims about generated verifier-backed tasks and observed model outputs are allowed.",
        "verifier_requirements": ["machine-readable task schema", "deterministic grader", "raw model output capture", "replication gate"],
        "datasets": ["synthetic verifier-generated tasks", "public model outputs only after secret scan"],
        "route": ["builder", "proof", "skeptic", "replicator", "publisher", "site", "release", "paper"],
        "expected_evidence_value": 94,
        "risk": 42,
        "first_objective": "create a minimal verifier-backed evaluation task schema with deterministic grading boundaries",
    },
    {
        "id": "formal_micro_conjecture_factory",
        "title": "Formal micro-conjecture discovery with counterexample-first gates",
        "objective_type": "real_research",
        "central_question": "Can autonomous agents generate small formal claims that are either proved or refuted by tools?",
        "claim_boundary": "Only machine-checked micro-claims or explicit counterexamples may be reported.",
        "verifier_requirements": ["symbolic checker", "counterexample search", "proof artifact hashes", "replication gate"],
        "datasets": ["synthetic algebraic and combinatorial micro-claims"],
        "route": ["builder", "proof", "skeptic", "replicator", "publisher", "site", "release", "paper"],
        "expected_evidence_value": 90,
        "risk": 30,
        "first_objective": "generate a counterexample-first formal micro-claim harness with explicit failure recording",
    },
    {
        "id": "algorithm_invariant_discovery",
        "title": "Algorithm invariant discovery under executable tests",
        "objective_type": "real_research",
        "central_question": "Can the system discover useful invariants for small algorithms and test them automatically?",
        "claim_boundary": "Only invariant candidates with executable checks and stored failures may be promoted.",
        "verifier_requirements": ["property tests", "seeded experiments", "raw failure corpus", "skeptic review"],
        "datasets": ["generated algorithm traces", "seeded randomized inputs"],
        "route": ["builder", "proof", "skeptic", "replicator", "publisher", "site", "release", "paper"],
        "expected_evidence_value": 86,
        "risk": 36,
        "first_objective": "build a seeded invariant-discovery artifact that preserves counterexamples as evidence",
    },
    {
        "id": "model_reliability_cartography",
        "title": "Model reliability cartography with reproducible failure maps",
        "objective_type": "real_research",
        "central_question": "Can model failure modes be mapped as reproducible families rather than anecdotal examples?",
        "claim_boundary": "Only measured failure-family observations with prompts, outputs, and reproduction metadata are allowed.",
        "verifier_requirements": ["prompt family schema", "response archive", "statistical boundary", "replication plan"],
        "datasets": ["public prompts", "redacted model responses"],
        "route": ["builder", "skeptic", "replicator", "publisher", "site", "release", "paper"],
        "expected_evidence_value": 82,
        "risk": 55,
        "first_objective": "define a failure-family schema for reproducible model reliability mapping without unsafe prompt publication",
    },
    {
        "id": "autonomous_science_methodology",
        "title": "Autonomous science methodology and anti-overclaim governance",
        "objective_type": "infrastructure_research",
        "central_question": "Which gates prevent autonomous systems from turning weak evidence into exaggerated public claims?",
        "claim_boundary": "Only governance, provenance, and reproducibility infrastructure claims are allowed.",
        "verifier_requirements": ["policy checks", "blocked-result ledger", "release gates", "paper-package gates"],
        "datasets": ["AxiomForge internal event log", "public ledger manifests"],
        "route": ["skeptic", "replicator", "publisher", "site", "release", "paper"],
        "expected_evidence_value": 74,
        "risk": 20,
        "first_objective": "measure whether blocked and negative results remain visible across the autonomous publication pipeline",
    },
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _priority(challenge: dict[str, Any]) -> int:
    route_bonus = 2 * len(challenge.get("route", []))
    real_research_bonus = 12 if challenge.get("objective_type") == "real_research" else 0
    return int(challenge["expected_evidence_value"]) + route_bonus + real_research_bonus - int(challenge["risk"])


def build_portfolio() -> dict[str, Any]:
    challenges = []
    for challenge in GRAND_CHALLENGES:
        item = dict(challenge)
        item["priority_score"] = _priority(challenge)
        item["publication_gate"] = {
            "requires_claim_boundary": True,
            "requires_verifier_requirements": True,
            "requires_skeptic_review": "skeptic" in item["route"],
            "requires_replication": "replicator" in item["route"],
            "requires_public_ledger": "publisher" in item["route"],
            "requires_release": "release" in item["route"],
            "requires_paper_package": "paper" in item["route"],
        }
        challenges.append(item)
    return {
        "generated_by": "AxiomForge Autonomous System",
        "generated_at": utc_now(),
        "phase": "phase8_grand_challenge_portfolio",
        "selection_rule": "maximize expected evidence value after risk and route completeness penalties; real research outranks maintenance when viable",
        "challenges": sorted(challenges, key=lambda item: (-item["priority_score"], item["id"])),
        "hard_limits": [
            "do not claim open problems are solved without machine-checkable or independently reproducible evidence",
            "do not let a single agent bypass skeptic or replication gates",
            "do not erase failed attempts or negative results",
            "do not optimize challenge selection for hype",
        ],
    }


def select_challenge(portfolio: dict[str, Any]) -> dict[str, Any]:
    real = [item for item in portfolio["challenges"] if item["objective_type"] == "real_research"]
    candidates = real or list(portfolio["challenges"])
    return sorted(candidates, key=lambda item: (-item["priority_score"], item["id"]))[0]


def negative_result_ledger(root: Path) -> dict[str, Any]:
    p = initialize(root)
    blocked: dict[str, int] = {}
    with db_session(p) as db:
        for table in [
            "tasks",
            "claims",
            "research_runs",
            "publication_queue",
            "code_runs",
            "proof_runs",
            "review_runs",
            "replication_runs",
            "release_runs",
            "paper_runs",
            "challenge_runs",
        ]:
            row = db.execute(f"SELECT COUNT(*) FROM {table} WHERE status IN ('blocked', 'failed', 'inconclusive')").fetchone()
            blocked[table] = int(row[0])
    return {
        "generated_by": "AxiomForge Autonomous System",
        "generated_at": utc_now(),
        "blocked_or_negative_counts": blocked,
        "policy": "negative results remain ledgered and may create follow-up tasks; they are not deleted to improve public appearance",
    }


def _route_plan(challenge: dict[str, Any]) -> dict[str, Any]:
    return {
        "challenge_id": challenge["id"],
        "objective": challenge["first_objective"],
        "route": challenge["route"],
        "stage_contracts": {
            "builder": "create bounded code artifact with tests and secret scan",
            "proof": "create machine-checkable verifier artifact or explicit counterexample",
            "skeptic": "attempt to block weak claims and overreach",
            "replicator": "rerun proof or experiment in a clean workspace",
            "publisher": "publish only queued, disclosed lab notes",
            "site": "render public ledger with claim type, evidence, limitations, and correction path",
            "release": "package immutable public ledger artifacts after gates pass",
            "paper": "prepare DOI/arXiv-ready package without external submission or human impersonation",
        },
    }


def _execute_route(root: Path, repo: Path, branch: str, challenge: dict[str, Any], *, push: bool, timeout_seconds: int) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    errors: list[str] = []
    objective = str(challenge["first_objective"])
    try:
        if "builder" in challenge["route"]:
            note = run_code_cycle(root, objective, timeout_seconds=timeout_seconds)
            steps.append({"stage": "builder", "status": "passed", "note": str(note)})
        if "proof" in challenge["route"]:
            note = run_proof_cycle(root, objective, timeout_seconds=max(timeout_seconds, 20))
            steps.append({"stage": "proof", "status": "passed", "note": str(note)})
        if "skeptic" in challenge["route"] or "replicator" in challenge["route"]:
            note = run_review_cycle(root, timeout_seconds=max(timeout_seconds, 20))
            steps.append({"stage": "skeptic_replicator", "status": "passed", "note": str(note)})
        if "publisher" in challenge["route"]:
            results = publish_ready_queue(root, repo, branch=branch, push=push)
            steps.append({"stage": "publisher", "status": "passed", "results": [result.__dict__ for result in results]})
        if "site" in challenge["route"]:
            result = publish_public_site(repo, branch=branch, push=push)
            steps.append({"stage": "site", "status": result.status, "pages": list(result.pages), "errors": list(result.errors)})
            if result.status != "passed":
                errors.extend(result.errors)
        if "release" in challenge["route"] and not errors:
            result = build_release_candidate(root, repo, branch=branch, push=push)
            steps.append({"stage": "release", "status": result.status, "manifest": result.manifest, "tag": result.tag, "errors": list(result.errors)})
            errors.extend(result.errors)
        if "paper" in challenge["route"] and not errors:
            result = build_paper_package(root, repo, branch=branch, push=push)
            steps.append({"stage": "paper", "status": result.status, "manifest": result.manifest, "tag": result.tag, "errors": list(result.errors)})
            errors.extend(result.errors)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        errors.append(str(exc)[:1000])
    return {
        "generated_by": "AxiomForge Autonomous System",
        "generated_at": utc_now(),
        "challenge_id": challenge["id"],
        "status": "passed" if not errors else "blocked",
        "steps": steps,
        "errors": errors,
    }


def run_challenge_cycle(
    root: Path,
    *,
    repo: Path | None = None,
    branch: str = DEFAULT_PUBLICATION_BRANCH,
    execute_route: bool = False,
    push: bool = True,
    timeout_seconds: int = 30,
) -> ChallengeResult:
    p = initialize(root)
    portfolio = build_portfolio()
    selected = select_challenge(portfolio)
    task_id = create_task(
        p,
        title=f"Phase 8 grand challenge route: {selected['title']}",
        kind="grand_challenge_research",
        payload={"challenge_id": selected["id"], "objective_type": selected["objective_type"]},
    )
    run_dir = p.artifacts / "challenge-runs" / f"{utc_now().replace(':', '').replace('+', 'Z')}-{slugify(selected['id'])}"
    run_dir.mkdir(parents=True, exist_ok=True)

    portfolio_path = run_dir / "portfolio.json"
    selected_path = run_dir / "selected_challenge.json"
    route_path = run_dir / "route_plan.json"
    negative_path = run_dir / "negative_results.json"
    route_result_path = run_dir / "route_result.json"
    manifest_path = run_dir / "manifest.json"

    route_plan = _route_plan(selected)
    negative = negative_result_ledger(root)
    route_result = {
        "generated_by": "AxiomForge Autonomous System",
        "generated_at": utc_now(),
        "challenge_id": selected["id"],
        "status": "planned",
        "steps": [],
        "errors": [],
    }
    if execute_route:
        if repo is None:
            route_result = {
                **route_result,
                "status": "blocked",
                "errors": ["execute_route requires a publication repo"],
            }
        else:
            route_result = _execute_route(root, repo.expanduser().resolve(), branch, selected, push=push, timeout_seconds=timeout_seconds)

    _write_json(portfolio_path, portfolio)
    _write_json(selected_path, selected)
    _write_json(route_path, route_plan)
    _write_json(negative_path, negative)
    _write_json(route_result_path, route_result)
    status = "verified" if route_result["status"] in {"planned", "passed"} else "blocked"
    challenge_payload = {
        "portfolio": str(portfolio_path),
        "selected_challenge": str(selected_path),
        "route_plan": str(route_path),
        "negative_results": str(negative_path),
        "route_result": str(route_result_path),
        "selected": selected,
    }
    run_id = register_challenge_run(p, challenge_id=selected["id"], status=status, challenge=challenge_payload)
    manifest = {
        "task_id": task_id,
        "challenge_run_id": run_id,
        "portfolio": str(portfolio_path),
        "selected_challenge": str(selected_path),
        "route_plan": str(route_path),
        "negative_results": str(negative_path),
        "route_result": str(route_result_path),
        "publication_eligible": status == "verified",
        "claim_boundary": selected["claim_boundary"],
    }
    _write_json(manifest_path, manifest)

    register_artifact(p, portfolio_path, "grand_challenge_portfolio", "Phase 8 machine-readable grand challenge portfolio")
    register_artifact(p, selected_path, "grand_challenge_selection", f"Selected challenge {selected['id']}")
    register_artifact(p, route_path, "grand_challenge_route_plan", f"Route plan for {selected['id']}")
    register_artifact(p, negative_path, "negative_result_ledger", "Blocked and negative result counts")
    register_artifact(p, route_result_path, "grand_challenge_route_result", f"Route execution result for {selected['id']}")
    register_artifact(p, manifest_path, "artifact_manifest", f"Phase 8 manifest for {selected['id']}")

    evidence = (
        f"task_id={task_id}; challenge_run_id={run_id}; portfolio={portfolio_path}; "
        f"selected={selected_path}; route={route_path}; negative_results={negative_path}; route_result={route_result_path}"
    )
    register_claim(
        p,
        "measured",
        "AxiomForge Phase 8 can select a bounded grand challenge portfolio item, define evidence gates, preserve negative-result counts, and route work through the autonomous research pipeline.",
        evidence,
        status="measured" if status == "verified" else "blocked",
    )
    body = f"""
## Observation

The autonomous system created a Phase 8 grand challenge portfolio and selected
`{selected['id']}` using expected evidence value, risk, route completeness, and
objective type. Infrastructure maintenance tasks are separated from real
research objectives through the `objective_type` field.

## Selected Challenge

```text
title={selected['title']}
objective_type={selected['objective_type']}
priority_score={selected['priority_score']}
claim_boundary={selected['claim_boundary']}
route={','.join(selected['route'])}
route_status={route_result['status']}
```

## Negative Result Ledger

```text
{json.dumps(negative['blocked_or_negative_counts'], sort_keys=True)}
```

## Evidence

```text
{evidence}
```

## Limitations

This cycle creates and optionally executes a bounded grand-challenge route. It
does not claim an open problem has been solved. Any scientific claim still
requires verifier artifacts, skeptic review, clean replication, public ledger
publication, release packaging, and paper packaging.
"""
    note = publish_lab_note(
        p,
        title="Phase 8 Grand Challenge Portfolio Cycle",
        claim_type="measured",
        body=body,
        evidence=evidence,
    )
    enqueue_publication(
        p,
        title="Phase 8 Grand Challenge Portfolio Cycle",
        path=note,
        target="github",
        status="ready" if status == "verified" else "blocked",
        policy={
            "autonomous_disclosure": True,
            "claim_type": "measured",
            "evidence": evidence,
            "challenge_id": selected["id"],
            "objective_type": selected["objective_type"],
            "claim_boundary": selected["claim_boundary"],
            "route_status": route_result["status"],
            "overclaim_block": True,
        },
    )
    if execute_route and repo is not None and route_result["status"] == "passed":
        final_errors: list[str] = []
        final_steps: list[dict[str, Any]] = []
        try:
            publish_results = publish_ready_queue(root, repo.expanduser().resolve(), branch=branch, push=push)
            final_steps.append(
                {
                    "stage": "challenge_note_publisher",
                    "status": "passed",
                    "results": [result.__dict__ for result in publish_results],
                }
            )
            site_result = publish_public_site(repo.expanduser().resolve(), branch=branch, push=push)
            final_steps.append(
                {
                    "stage": "challenge_note_site",
                    "status": site_result.status,
                    "pages": list(site_result.pages),
                    "errors": list(site_result.errors),
                }
            )
            final_errors.extend(site_result.errors)
            if not final_errors:
                release_result = build_release_candidate(root, repo.expanduser().resolve(), branch=branch, push=push)
                final_steps.append(
                    {
                        "stage": "challenge_note_release",
                        "status": release_result.status,
                        "manifest": release_result.manifest,
                        "tag": release_result.tag,
                        "errors": list(release_result.errors),
                    }
                )
                final_errors.extend(release_result.errors)
            if not final_errors:
                paper_result = build_paper_package(root, repo.expanduser().resolve(), branch=branch, push=push)
                final_steps.append(
                    {
                        "stage": "challenge_note_paper",
                        "status": paper_result.status,
                        "manifest": paper_result.manifest,
                        "tag": paper_result.tag,
                        "errors": list(paper_result.errors),
                    }
                )
                final_errors.extend(paper_result.errors)
        except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
            final_errors.append(str(exc)[:1000])
        route_result["steps"].extend(final_steps)
        route_result["errors"].extend(final_errors)
        route_result["status"] = "passed" if not route_result["errors"] else "blocked"
        _write_json(route_result_path, route_result)
        status = "verified" if route_result["status"] == "passed" else "blocked"
        challenge_payload["route_result"] = str(route_result_path)
        update_challenge_run(p, run_id, status=status, challenge=challenge_payload)

    return ChallengeResult(selected["id"], status, str(manifest_path), route_result["status"], tuple(route_result["errors"]))
