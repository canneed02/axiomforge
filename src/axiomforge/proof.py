from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .kernel import (
    create_task,
    enqueue_publication,
    initialize,
    publish_lab_note,
    register_artifact,
    register_claim,
    register_proof_run,
    slugify,
    utc_now,
)


DEFAULT_TIMEOUT_SECONDS = 45


@dataclass(frozen=True)
class HarnessResult:
    name: str
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    parsed: dict[str, Any]

    def public_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout[-6000:],
            "stderr": self.stderr[-6000:],
            "timed_out": self.timed_out,
            "parsed": self.parsed,
        }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_write(workspace: Path, relative_path: str, content: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe relative path: {relative_path}")
    target = (workspace / relative).resolve()
    if not target.is_relative_to(workspace.resolve()):
        raise ValueError(f"path escapes workspace: {relative_path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return target


def _symbolic_script() -> str:
    return r'''from __future__ import annotations

import json
import sympy as sp

x = sp.symbols("x")
identity = sp.expand((x + 1) ** 3 - (x**3 + 3 * x**2 + 3 * x + 1))
normal_form = sp.simplify(identity)
status = "proved" if normal_form == 0 else "inconclusive"

print(json.dumps({
    "tool": "sympy",
    "tool_version": sp.__version__,
    "claim": "For all symbolic x, (x + 1)^3 equals x^3 + 3*x^2 + 3*x + 1.",
    "method": "expand and simplify polynomial identity to normal form",
    "status": status,
    "normal_form": str(normal_form),
    "machine_checkable": True,
}, sort_keys=True))
'''


def _empirical_script() -> str:
    return r'''from __future__ import annotations

import collections
import json
import random
import sys

seed = 20260526
rng = random.Random(seed)
trials = 200
failures = []
for trial in range(trials):
    values = [rng.randint(-1000, 1000) for _ in range(64)]
    observed = sorted(values)
    nondecreasing = all(observed[i] <= observed[i + 1] for i in range(len(observed) - 1))
    same_multiset = collections.Counter(values) == collections.Counter(observed)
    if not nondecreasing or not same_multiset:
        failures.append({
            "trial": trial,
            "nondecreasing": nondecreasing,
            "same_multiset": same_multiset,
            "input": values,
            "output": observed,
        })
        break

print(json.dumps({
    "tool": "python",
    "tool_version": sys.version.split()[0],
    "claim": "Python sorted returns a nondecreasing sequence preserving the input multiset for generated integer lists.",
    "method": "deterministic seeded empirical invariant check",
    "seed": seed,
    "trials": trials,
    "status": "replicated" if not failures else "counterexample",
    "failures": failures,
    "machine_checkable": True,
}, sort_keys=True))
'''


def run_harness(workspace: Path, name: str, script: Path, timeout_seconds: int) -> HarnessResult:
    command = [sys.executable, str(script.relative_to(workspace))]
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        parsed: dict[str, Any] = {}
        if completed.stdout.strip():
            try:
                parsed = json.loads(completed.stdout)
            except json.JSONDecodeError:
                parsed = {"parse_error": "stdout is not valid JSON"}
        return HarnessResult(name, command, completed.returncode, completed.stdout, completed.stderr, False, parsed)
    except subprocess.TimeoutExpired as exc:
        return HarnessResult(
            name,
            command,
            124,
            exc.stdout if isinstance(exc.stdout, str) else "",
            exc.stderr if isinstance(exc.stderr, str) else "",
            True,
            {"status": "inconclusive", "timeout": True},
        )


def build_verifier(objective: str, results: list[HarnessResult]) -> dict[str, Any]:
    statuses = {result.name: result.parsed.get("status", "inconclusive") for result in results}
    commands_ok = all(result.exit_code == 0 and not result.timed_out for result in results)
    symbolic_ok = statuses.get("symbolic") == "proved"
    empirical_ok = statuses.get("empirical") == "replicated"
    if not commands_ok:
        status = "inconclusive"
    elif any(value == "counterexample" for value in statuses.values()):
        status = "counterexample"
    elif symbolic_ok and empirical_ok:
        status = "verified"
    else:
        status = "inconclusive"
    return {
        "generated_by": "AxiomForge autonomous research system",
        "generated_at": utc_now(),
        "phase": "phase3_proof_experiment_harness",
        "objective": objective,
        "status": status,
        "checks": {
            "commands_ok": commands_ok,
            "symbolic_proved": symbolic_ok,
            "empirical_replicated": empirical_ok,
            "has_machine_checkable_outputs": all(result.parsed.get("machine_checkable") is True for result in results),
        },
        "harness_statuses": statuses,
        "claim_boundary": "symbolic proof covers the polynomial identity; empirical result covers deterministic generated samples only",
        "limitations": [
            "the symbolic proof target is a bounded identity check, not a broad theorem discovery result",
            "the empirical harness demonstrates deterministic experiment capture, not universal program correctness",
            "future phases must add adversarial skeptic and clean replication gates",
        ],
    }


def run_proof_cycle(root: Path, objective: str, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Path:
    p = initialize(root)
    task_id = create_task(p, title=f"Phase 3 proof/experiment cycle: {objective}", kind="proof_experiment_cycle", payload={"objective": objective})
    run_dir = p.artifacts / "proof-runs" / f"{utc_now().replace(':', '').replace('+', 'Z')}-{slugify(objective)}"
    workspace = run_dir / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    symbolic_script = _safe_write(workspace, "harnesses/symbolic_identity.py", _symbolic_script())
    empirical_script = _safe_write(workspace, "harnesses/empirical_sort_invariant.py", _empirical_script())
    results = [
        run_harness(workspace, "symbolic", symbolic_script, timeout_seconds),
        run_harness(workspace, "empirical", empirical_script, timeout_seconds),
    ]
    verifier = build_verifier(objective, results)
    passed = verifier["status"] == "verified"

    raw_path = run_dir / "raw_results.json"
    verifier_path = run_dir / "verifier.json"
    manifest_path = run_dir / "manifest.json"
    raw_payload = {"results": [result.public_dict() for result in results]}
    _write_json(raw_path, raw_payload)
    _write_json(verifier_path, verifier)
    manifest = {
        "raw_results": str(raw_path),
        "verifier": str(verifier_path),
        "workspace": str(workspace),
        "hashes": {
            "raw_results": _sha256(raw_path),
            "verifier": _sha256(verifier_path),
            "symbolic_script": _sha256(symbolic_script),
            "empirical_script": _sha256(empirical_script),
        },
    }
    _write_json(manifest_path, manifest)

    register_artifact(p, raw_path, "proof_experiment_raw_results", f"Phase 3 raw results for task {task_id}")
    register_artifact(p, verifier_path, "proof_experiment_verifier", f"Phase 3 verifier for task {task_id}")
    register_artifact(p, manifest_path, "artifact_manifest", f"Phase 3 artifact manifest for task {task_id}")
    proof_run_id = register_proof_run(
        p,
        objective=objective,
        workspace=workspace,
        status="verified" if passed else verifier["status"],
        verifier=verifier,
    )
    evidence = f"task_id={task_id}; proof_run_id={proof_run_id}; raw={raw_path}; verifier={verifier_path}; manifest={manifest_path}"
    register_claim(
        p,
        "measured",
        "AxiomForge Phase 3 can run bounded symbolic and deterministic empirical harnesses, record raw evidence, and generate a verifier artifact.",
        evidence,
        status="measured" if passed else "blocked",
    )

    body = f"""
## Observation

The autonomous system ran a Phase 3 proof/experiment cycle for `{objective}`.
It executed a SymPy symbolic identity harness and a deterministic seeded
empirical invariant harness inside a bounded workspace, then wrote raw command
outputs, verifier status, scripts, and artifact hashes.

## Verifier Result

```text
status={verifier["status"]}
symbolic={verifier["harness_statuses"].get("symbolic")}
empirical={verifier["harness_statuses"].get("empirical")}
```

## Evidence

```text
{evidence}
```

## Limitations

This autonomous cycle validates proof and experiment infrastructure. It does
not claim a new theorem, does not claim universal empirical correctness, and
does not bypass future skeptic or clean-replication gates.
"""
    note = publish_lab_note(
        p,
        title="Phase 3 Proof Experiment Cycle",
        claim_type="measured",
        body=body,
        evidence=evidence,
    )
    enqueue_publication(
        p,
        title="Phase 3 Proof Experiment Cycle",
        path=note,
        target="github",
        status="ready" if passed else "blocked",
        policy={
            "autonomous_disclosure": True,
            "claim_type": "measured",
            "evidence": evidence,
            "verifier_status": verifier["status"],
            "symbolic_proved": verifier["checks"]["symbolic_proved"],
            "empirical_replicated": verifier["checks"]["empirical_replicated"],
            "review_required_before_claiming_science": True,
        },
    )
    return note
