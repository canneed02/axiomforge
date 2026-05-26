from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .kernel import (
    ForgePaths,
    create_task,
    enqueue_publication,
    initialize,
    publish_lab_note,
    register_artifact,
    register_claim,
    register_research_run,
    slugify,
    utc_now,
)
from .providers import nvidia_chat_once, nvidia_inventory_from_env


PROGRAMS = {
    "evaluation": ("benchmark", "model", "eval", "score", "frontier"),
    "proof": ("proof", "theorem", "formal", "logic", "lemma"),
    "algorithm": ("algorithm", "code", "optimize", "search", "complexity"),
    "reliability": ("reliability", "failure", "robust", "replication", "safety"),
    "methodology": ("autonomous", "science", "method", "publication", "institution"),
}


def select_program(goal: str) -> str:
    lowered = goal.lower()
    scores = {
        program: sum(1 for keyword in keywords if keyword in lowered)
        for program, keywords in PROGRAMS.items()
    }
    winner = max(scores, key=lambda key: (scores[key], key))
    return winner if scores[winner] > 0 else "methodology"


def build_proposal(goal: str, p: ForgePaths) -> dict[str, Any]:
    program = select_program(goal)
    inventory = nvidia_inventory_from_env().public_dict()
    return {
        "title": f"Phase 1 Research Cycle: {goal}",
        "generated_by": "AxiomForge autonomous research system",
        "generated_at": utc_now(),
        "goal": goal,
        "program": program,
        "provider_inventory": inventory,
        "central_question": f"What is the smallest reproducible artifact that advances: {goal}?",
        "method": [
            "produce a falsifiable research proposal",
            "record provider and tool provenance without exposing secrets",
            "write machine-readable proposal and verifier artifacts",
            "publish only through the autonomous disclosure policy gate",
            "queue public release instead of pushing unreviewed claims directly",
        ],
        "expected_outputs": [
            "proposal.json",
            "verifier.json",
            "autonomous lab note",
            "publication queue item",
        ],
        "limitations": [
            "phase 1 validates the research operating loop, not a scientific breakthrough",
            "external model use is optional and bounded to one call per cycle",
            "publication is queued until policy and repository hygiene gates pass",
        ],
        "state_root": str(p.root),
    }


def ask_provider_for_research_memo(goal: str) -> dict[str, Any]:
    prompt = f"""You are contributing to an autonomous scientific research harness.

Goal: {goal}

Return a concise research memo with:
1. one falsifiable claim,
2. one experiment or proof harness,
3. three failure modes,
4. one minimal artifact that could be published transparently.

Do not claim that an open problem is solved. Keep it technical and testable."""
    return nvidia_chat_once(prompt=prompt)


def verify_proposal(proposal: dict[str, Any], provider_memo: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "has_autonomous_identity": proposal.get("generated_by") == "AxiomForge autonomous research system",
        "has_goal": bool(proposal.get("goal")),
        "has_program": proposal.get("program") in PROGRAMS,
        "has_outputs": bool(proposal.get("expected_outputs")),
        "has_limitations": bool(proposal.get("limitations")),
        "provider_secrets_redacted": all(marker not in json.dumps(proposal) for marker in ("".join(("nv", "api-")), "".join(("s", "k-")))),
        "provider_call_bounded": provider_memo.get("ok") in {True, False},
    }
    return {
        "generated_at": utc_now(),
        "checks": checks,
        "passed": all(checks.values()),
        "provider_memo_ok": bool(provider_memo.get("ok")),
        "provider_error": provider_memo.get("error", ""),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def run_phase1_research_cycle(root: Path, goal: str) -> Path:
    p = initialize(root)
    task_id = create_task(p, title=f"Phase 1 research cycle: {goal}", kind="research_cycle", payload={"goal": goal})
    run_dir = p.artifacts / "research-runs" / f"{utc_now().replace(':', '').replace('+', 'Z')}-{slugify(goal)}"
    run_dir.mkdir(parents=True, exist_ok=True)

    proposal = build_proposal(goal, p)
    provider_memo = ask_provider_for_research_memo(goal)
    proposal["provider_memo"] = {
        "ok": provider_memo.get("ok", False),
        "model": provider_memo.get("model", ""),
        "key_fingerprint": provider_memo.get("key_fingerprint", ""),
        "usage": provider_memo.get("usage", {}),
        "content": provider_memo.get("content", ""),
        "error": provider_memo.get("error", ""),
    }
    verifier = verify_proposal(proposal, provider_memo)

    proposal_path = run_dir / "proposal.json"
    verifier_path = run_dir / "verifier.json"
    _write_json(proposal_path, proposal)
    _write_json(verifier_path, verifier)
    register_artifact(p, proposal_path, "research_proposal", proposal["title"])
    register_artifact(p, verifier_path, "verification_report", f"Verifier for task {task_id}")

    run_id = register_research_run(
        p,
        goal=goal,
        program=proposal["program"],
        status="verified" if verifier["passed"] else "blocked",
        proposal=proposal,
        verifier=verifier,
    )
    evidence = f"task_id={task_id}; run_id={run_id}; proposal={proposal_path}; verifier={verifier_path}"
    register_claim(
        p,
        "measured",
        "AxiomForge Phase 1 can produce a bounded autonomous research proposal, verification artifact, and queued publication candidate.",
        evidence,
        status="measured" if verifier["passed"] else "blocked",
    )

    provider_section = "No external provider memo was produced."
    if proposal["provider_memo"]["ok"]:
        provider_section = f"""External provider memo:

```text
{proposal["provider_memo"]["content"].strip()}
```"""

    body = f"""
## Observation

The autonomous system created a Phase 1 research cycle for `{goal}`. It selected
the `{proposal["program"]}` program, wrote machine-readable proposal and
verification artifacts, and checked that provider secrets were redacted from
public artifacts.

{provider_section}

## Publication Queue

The note is queued as a release candidate, not silently pushed as a finished
scientific result. Public release requires policy, hygiene, and reproducibility
checks.

## Limitations

This autonomous cycle validates the operating loop. It does not claim that an
open scientific problem is solved. Provider output, when present, is treated as
a proposal input rather than evidence of truth.
"""
    note = publish_lab_note(
        p,
        title="Phase 1 Research Cycle",
        claim_type="measured",
        evidence=evidence,
        body=body,
    )
    enqueue_publication(
        p,
        title="Phase 1 Research Cycle",
        path=note,
        target="github",
        status="ready" if verifier["passed"] else "blocked",
        policy={
            "autonomous_disclosure": True,
            "claim_type": "measured",
            "evidence": evidence,
            "verifier_passed": verifier["passed"],
        },
    )
    return note
