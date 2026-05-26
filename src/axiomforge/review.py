from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from .kernel import (
    create_task,
    enqueue_publication,
    initialize,
    latest_proof_run,
    publish_lab_note,
    register_artifact,
    register_claim,
    register_replication_run,
    register_review_run,
    slugify,
    utc_now,
)
from .proof import build_verifier, run_harness


DEFAULT_TIMEOUT_SECONDS = 45


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _run_dir_from_workspace(workspace: Path) -> Path:
    if workspace.name != "workspace":
        raise ValueError(f"expected proof workspace path, got: {workspace}")
    return workspace.parent


def build_skeptic_review(subject: dict[str, Any], raw: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    verifier = subject["verifier"]
    objections: list[dict[str, str]] = []
    if verifier.get("status") != "verified":
        objections.append({"severity": "critical", "message": "verifier status is not verified", "required_fix": "rerun or repair proof-cycle"})
    if not verifier.get("checks", {}).get("has_machine_checkable_outputs"):
        objections.append({"severity": "critical", "message": "machine-checkable outputs are missing", "required_fix": "include parsed harness outputs"})
    if not manifest.get("hashes"):
        objections.append({"severity": "high", "message": "artifact hashes are missing", "required_fix": "write manifest hashes"})
    if not raw.get("results"):
        objections.append({"severity": "critical", "message": "raw harness results are missing", "required_fix": "store raw results"})
    boundary = str(verifier.get("claim_boundary", "")).lower()
    if "boundary" not in boundary and "covers" not in boundary:
        objections.append({"severity": "medium", "message": "claim boundary is vague", "required_fix": "state proof and experiment scope"})
    objections.append(
        {
            "severity": "info",
            "message": "Phase 4 accepts this only as infrastructure validation, not a new scientific theorem.",
            "required_fix": "keep public claim type measured",
        }
    )
    blocking = {"critical", "high"}
    passed = not any(objection["severity"] in blocking for objection in objections)
    return {
        "generated_by": "AxiomForge Skeptic Agent",
        "generated_at": utc_now(),
        "subject_type": "proof_run",
        "subject_id": subject["id"],
        "status": "passed" if passed else "blocked",
        "objections": objections,
        "read_inputs": {
            "verifier_status": verifier.get("status"),
            "harness_statuses": verifier.get("harness_statuses", {}),
            "manifest_hash_count": len(manifest.get("hashes", {})),
            "raw_result_count": len(raw.get("results", [])),
        },
        "limitations": [
            "skeptic review is rule-based in Phase 4",
            "model-generated review text is not treated as proof",
            "future phases should add independent model and human-readable critique layers",
        ],
    }


def replicate_proof_run(subject: dict[str, Any], clean_workspace: Path, timeout_seconds: int) -> dict[str, Any]:
    original_workspace = Path(subject["workspace"])
    original_run_dir = _run_dir_from_workspace(original_workspace)
    source_harnesses = original_workspace / "harnesses"
    if not source_harnesses.exists():
        return {
            "generated_by": "AxiomForge Replicator Agent",
            "generated_at": utc_now(),
            "subject_type": "proof_run",
            "subject_id": subject["id"],
            "status": "failed",
            "error": "original harness directory is missing",
        }

    clean_workspace.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_harnesses, clean_workspace / "harnesses")
    symbolic = clean_workspace / "harnesses" / "symbolic_identity.py"
    empirical = clean_workspace / "harnesses" / "empirical_sort_invariant.py"
    results = [
        run_harness(clean_workspace, "symbolic", symbolic, timeout_seconds),
        run_harness(clean_workspace, "empirical", empirical, timeout_seconds),
    ]
    verifier = build_verifier(subject["objective"], results)
    original_verifier = subject["verifier"]
    expected_status = original_verifier.get("status")
    same_status = verifier.get("status") == expected_status
    harness_statuses_match = verifier.get("harness_statuses") == original_verifier.get("harness_statuses")
    passed = verifier.get("status") == "verified" and same_status and harness_statuses_match
    commands = [result.public_dict() for result in results]
    return {
        "generated_by": "AxiomForge Replicator Agent",
        "generated_at": utc_now(),
        "subject_type": "proof_run",
        "subject_id": subject["id"],
        "status": "passed" if passed else "failed",
        "original_run_dir": str(original_run_dir),
        "clean_workspace": str(clean_workspace),
        "python": sys.version.split()[0],
        "commands": commands,
        "replicated_verifier": verifier,
        "comparisons": {
            "same_status": same_status,
            "harness_statuses_match": harness_statuses_match,
            "expected_status": expected_status,
            "observed_status": verifier.get("status"),
        },
        "hashes": {
            "symbolic_script": _sha256(symbolic),
            "empirical_script": _sha256(empirical),
        },
        "limitations": [
            "replication reruns copied harness scripts in a clean workspace",
            "it does not yet rebuild the entire repository from a fresh clone",
        ],
    }


def run_review_cycle(root: Path, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Path:
    p = initialize(root)
    subject = latest_proof_run(p)
    if not subject:
        raise ValueError("no proof run is available for review")
    task_id = create_task(
        p,
        title=f"Phase 4 review/replication cycle for proof_run {subject['id']}",
        kind="review_replication_cycle",
        payload={"subject_type": "proof_run", "subject_id": subject["id"]},
    )
    source_workspace = Path(subject["workspace"])
    source_run_dir = _run_dir_from_workspace(source_workspace)
    raw_path = source_run_dir / "raw_results.json"
    manifest_path = source_run_dir / "manifest.json"
    verifier_path = source_run_dir / "verifier.json"
    raw = _load_json(raw_path)
    manifest = _load_json(manifest_path)

    run_dir = p.artifacts / "review-runs" / f"{utc_now().replace(':', '').replace('+', 'Z')}-proof-run-{subject['id']}"
    clean_workspace = run_dir / "replication-workspace"
    review = build_skeptic_review(subject, raw, manifest)
    replication = replicate_proof_run(subject, clean_workspace, timeout_seconds)
    gate_passed = review["status"] == "passed" and replication["status"] == "passed"
    gate = {
        "generated_by": "AxiomForge policy gate",
        "generated_at": utc_now(),
        "subject_type": "proof_run",
        "subject_id": subject["id"],
        "status": "passed" if gate_passed else "blocked",
        "review_status": review["status"],
        "replication_status": replication["status"],
        "publication_eligible": gate_passed,
    }

    review_path = run_dir / "skeptic_review.json"
    replication_path = run_dir / "replication.json"
    gate_path = run_dir / "gate.json"
    manifest_out_path = run_dir / "manifest.json"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(review_path, review)
    _write_json(replication_path, replication)
    _write_json(gate_path, gate)
    manifest_out = {
        "subject_verifier": str(verifier_path),
        "subject_raw": str(raw_path),
        "subject_manifest": str(manifest_path),
        "skeptic_review": str(review_path),
        "replication": str(replication_path),
        "gate": str(gate_path),
        "hashes": {
            "skeptic_review": _sha256(review_path),
            "replication": _sha256(replication_path),
            "gate": _sha256(gate_path),
        },
    }
    _write_json(manifest_out_path, manifest_out)

    register_artifact(p, review_path, "skeptic_review", f"Phase 4 skeptic review for proof_run {subject['id']}")
    register_artifact(p, replication_path, "replication_report", f"Phase 4 replication report for proof_run {subject['id']}")
    register_artifact(p, gate_path, "publication_gate", f"Phase 4 publication gate for proof_run {subject['id']}")
    register_artifact(p, manifest_out_path, "artifact_manifest", f"Phase 4 artifact manifest for proof_run {subject['id']}")
    review_id = register_review_run(
        p,
        subject_type="proof_run",
        subject_id=subject["id"],
        status=review["status"],
        review=review,
    )
    replication_id = register_replication_run(
        p,
        subject_type="proof_run",
        subject_id=subject["id"],
        status=replication["status"],
        replication=replication,
    )
    if not gate_passed:
        create_task(
            p,
            title=f"Repair blocked Phase 4 gate for proof_run {subject['id']}",
            kind="follow_up",
            payload={"review_status": review["status"], "replication_status": replication["status"]},
        )
    evidence = (
        f"task_id={task_id}; review_id={review_id}; replication_id={replication_id}; "
        f"review={review_path}; replication={replication_path}; gate={gate_path}"
    )
    register_claim(
        p,
        "measured",
        "AxiomForge Phase 4 can run skeptic review and clean replication gates before publication eligibility.",
        evidence,
        status="measured" if gate_passed else "blocked",
    )
    body = f"""
## Observation

The autonomous system ran a Phase 4 review and replication cycle for
`proof_run {subject['id']}`. The Skeptic Agent read verifier, raw result, and
manifest artifacts before publication eligibility. The Replicator Agent reran
the proof and experiment harnesses in a clean workspace and compared verifier
status against the original run.

## Gate Result

```text
gate={gate["status"]}
review={review["status"]}
replication={replication["status"]}
```

## Evidence

```text
{evidence}
```

## Limitations

This autonomous cycle validates review and replication gates. The skeptic is
rule-based in this phase, replication reruns copied harness scripts, and model
review text is not treated as proof.
"""
    note = publish_lab_note(
        p,
        title="Phase 4 Review Replication Cycle",
        claim_type="measured",
        body=body,
        evidence=evidence,
    )
    enqueue_publication(
        p,
        title="Phase 4 Review Replication Cycle",
        path=note,
        target="github",
        status="ready" if gate_passed else "blocked",
        policy={
            "autonomous_disclosure": True,
            "claim_type": "measured",
            "evidence": evidence,
            "skeptic_review_passed": review["status"] == "passed",
            "replication_passed": replication["status"] == "passed",
            "publication_gate": gate["status"],
        },
    )
    return note
