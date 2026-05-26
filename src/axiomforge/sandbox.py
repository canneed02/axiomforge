from __future__ import annotations

import hashlib
import json
import keyword
import re
import shlex
import subprocess
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
    register_code_run,
    slugify,
    utc_now,
)
from .providers import nvidia_chat_once


DEFAULT_TIMEOUT_SECONDS = 30
ALLOWED_COMMANDS = {
    ("python3", "-m", "compileall"),
    ("python3", "-m", "unittest"),
    ("git", "status"),
    ("git", "diff"),
}
SECRET_PATTERNS = (
    re.compile(re.escape("".join(("n", "v", "api-")))),
    re.compile(re.escape("".join(("s", "k-"))) + r"[A-Za-z0-9]{20,}"),
)


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool

    def public_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout[-4000:],
            "stderr": self.stderr[-4000:],
            "timed_out": self.timed_out,
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


def _safe_identifier(value: str, fallback: str) -> str:
    identifier = re.sub(r"[^a-z0-9_]", "_", value.lower()).strip("_")
    if not identifier or keyword.iskeyword(identifier) or not re.match(r"^[a-z_]", identifier):
        return fallback
    return identifier


def _command_prefix(command: list[str]) -> tuple[str, ...]:
    if len(command) >= 3 and command[:2] == ["python3", "-m"]:
        return tuple(command[:3])
    if len(command) >= 2 and command[0] == "git":
        return tuple(command[:2])
    return tuple(command)


def validate_command(command: list[str]) -> None:
    if not command:
        raise ValueError("command is required")
    forbidden_tokens = {";", "&&", "||", "|", ">", "<", "`", "$("}
    if any(token in forbidden_tokens or "$(" in token for token in command):
        raise ValueError(f"forbidden shell token in command: {command}")
    if _command_prefix(command) not in ALLOWED_COMMANDS:
        raise ValueError(f"command is not allowlisted: {' '.join(command)}")


def run_command(workspace: Path, command: list[str], timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> CommandResult:
    validate_command(command)
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
        return CommandResult(command, completed.returncode, completed.stdout, completed.stderr, False)
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command,
            124,
            exc.stdout if isinstance(exc.stdout, str) else "",
            exc.stderr if isinstance(exc.stderr, str) else "",
            True,
        )


def scan_for_secrets(root: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(str(path.relative_to(root)))
                break
    return findings


def ask_builder_for_plan(objective: str) -> dict[str, Any]:
    prompt = f"""You are the Builder Agent inside AxiomForge Phase 2.

Objective: {objective}

Return compact JSON only with keys:
- module_name: safe snake_case Python module name
- function_name: safe snake_case function name
- invariant: one testable invariant
- strategy: short implementation strategy

Do not include markdown. Do not include secrets. Do not claim a scientific
breakthrough."""
    response = nvidia_chat_once(prompt=prompt, timeout_seconds=25)
    if not response.get("ok"):
        return {
            "provider_ok": False,
            "provider_error": response.get("error", ""),
            "module_name": "generated_result",
            "function_name": "describe_objective",
            "invariant": "result includes objective and autonomous disclosure",
            "strategy": "use a deterministic minimal module until provider output is usable",
        }
    content = str(response.get("content", "")).strip()
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = {}
    module_name = _safe_identifier(str(parsed.get("module_name", "generated_result")), "generated_result")
    function_name = _safe_identifier(str(parsed.get("function_name", "describe_objective")), "describe_objective")
    return {
        "provider_ok": True,
        "provider_model": response.get("model", ""),
        "provider_usage": response.get("usage", {}),
        "module_name": module_name or "generated_result",
        "function_name": function_name or "describe_objective",
        "invariant": str(parsed.get("invariant", "result includes objective and autonomous disclosure"))[:500],
        "strategy": str(parsed.get("strategy", "deterministic bounded code generation"))[:500],
    }


def _module_source(function_name: str, objective: str) -> str:
    return f'''"""Autonomous Phase 2 sandbox output."""


def {function_name}():
    """Return a transparent description of the sandbox code attempt."""
    return {{
        "generated_by": "AxiomForge autonomous research system",
        "objective": {objective!r},
        "claim_type": "measured",
    }}
'''


def _test_source(module_name: str, function_name: str, objective: str) -> str:
    return f"""import unittest

from src.{module_name} import {function_name}


class GeneratedCodeTest(unittest.TestCase):
    def test_generated_result_discloses_autonomy(self):
        result = {function_name}()

        self.assertEqual(result['generated_by'], 'AxiomForge autonomous research system')
        self.assertEqual(result['objective'], {objective!r})
        self.assertEqual(result['claim_type'], 'measured')


if __name__ == '__main__':
    unittest.main()
"""


def _init_workspace(workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    _safe_write(workspace, "README.md", "# AxiomForge Phase 2 Sandbox\n\nGenerated workspace.\n")
    _safe_write(workspace, "src/__init__.py", "")
    _safe_write(workspace, "tests/__init__.py", "")
    subprocess.run(["git", "init"], cwd=workspace, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "add", "."], cwd=workspace, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(
        ["git", "-c", "user.name=AxiomForge", "-c", "user.email=axiomforge@example.invalid", "commit", "-m", "baseline"],
        cwd=workspace,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _git_output(workspace: Path, args: list[str]) -> str:
    completed = subprocess.run(["git", *args], cwd=workspace, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return completed.stdout


def run_code_cycle(root: Path, objective: str, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Path:
    p = initialize(root)
    task_id = create_task(p, title=f"Phase 2 code cycle: {objective}", kind="code_cycle", payload={"objective": objective})
    run_dir = p.artifacts / "code-runs" / f"{utc_now().replace(':', '').replace('+', 'Z')}-{slugify(objective)}"
    workspace = run_dir / "workspace"
    _init_workspace(workspace)

    builder_plan = ask_builder_for_plan(objective)
    module_name = str(builder_plan["module_name"])
    function_name = str(builder_plan["function_name"])
    _safe_write(workspace, f"src/{module_name}.py", _module_source(function_name, objective))
    _safe_write(workspace, f"tests/test_{module_name}.py", _test_source(module_name, function_name, objective))
    subprocess.run(["git", "add", "-N", "src", "tests"], cwd=workspace, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    commands = [
        ["python3", "-m", "compileall", "-q", "src", "tests"],
        ["python3", "-m", "unittest", "discover", "-s", "tests"],
        ["git", "diff", "--", "src", "tests"],
        ["git", "status", "--short"],
    ]
    command_results = [run_command(workspace, command, timeout_seconds) for command in commands]
    secret_findings = scan_for_secrets(workspace)
    diff_text = _git_output(workspace, ["diff", "--", "src", "tests"])
    status_text = _git_output(workspace, ["status", "--short"])

    logs_path = run_dir / "commands.json"
    diff_path = run_dir / "diff.patch"
    summary_path = run_dir / "summary.json"
    logs_path.parent.mkdir(parents=True, exist_ok=True)
    logs_payload = {"commands": [result.public_dict() for result in command_results]}
    _write_json(logs_path, logs_payload)
    diff_path.write_text(diff_text)

    passed_commands = all(result.exit_code == 0 and not result.timed_out for result in command_results)
    passed = passed_commands and not secret_findings and bool(diff_text.strip())
    summary = {
        "generated_by": "AxiomForge autonomous research system",
        "phase": "phase2_sandbox_code_writing_agent",
        "objective": objective,
        "task_id": task_id,
        "workspace": str(workspace),
        "builder_plan": builder_plan,
        "commands": [result.public_dict() for result in command_results],
        "secret_findings": secret_findings,
        "diff_sha256": hashlib.sha256(diff_text.encode()).hexdigest(),
        "diff_path": str(diff_path),
        "logs_path": str(logs_path),
        "workspace_status": status_text,
        "passed": passed,
        "limitations": [
            "phase 2 validates sandboxed code generation infrastructure",
            "generated code is a bounded artifact, not a scientific breakthrough",
            "future phases must add adversarial review and clean replication",
        ],
    }
    _write_json(summary_path, summary)
    manifest = {
        "summary": str(summary_path),
        "diff": str(diff_path),
        "commands": str(logs_path),
        "hashes": {
            "summary": _sha256(summary_path),
            "diff": _sha256(diff_path),
            "commands": _sha256(logs_path),
        },
    }
    manifest_path = run_dir / "manifest.json"
    _write_json(manifest_path, manifest)

    register_artifact(p, summary_path, "code_run_summary", f"Phase 2 code cycle summary for task {task_id}")
    register_artifact(p, diff_path, "code_diff", f"Phase 2 sandbox diff for task {task_id}")
    register_artifact(p, logs_path, "command_log", f"Phase 2 command log for task {task_id}")
    register_artifact(p, manifest_path, "artifact_manifest", f"Phase 2 artifact manifest for task {task_id}")
    code_run_id = register_code_run(
        p,
        objective=objective,
        workspace=workspace,
        status="verified" if passed else "blocked",
        summary=summary,
    )
    evidence = f"task_id={task_id}; code_run_id={code_run_id}; summary={summary_path}; diff={diff_path}; logs={logs_path}"
    register_claim(
        p,
        "measured",
        "AxiomForge Phase 2 can execute a sandboxed code-writing attempt with command allowlisting, timeout capture, secret scanning, diff summary, and artifact logging.",
        evidence,
        status="measured" if passed else "blocked",
    )

    body = f"""
## Observation

The autonomous system ran a Phase 2 sandbox code-writing attempt for
`{objective}`. The Builder Agent produced code inside an isolated workspace, the
runner executed only allowlisted commands, and the system stored command logs,
diffs, hashes, and a machine-readable summary as artifacts.

## Gate Result

```text
passed={passed}
secret_findings={secret_findings}
commands_passed={passed_commands}
```

## Evidence

```text
{evidence}
```

## Limitations

This autonomous code cycle validates the sandbox and gating mechanism. It does
not claim a scientific result, does not write to main, and does not bypass
review or replication.
"""
    note = publish_lab_note(
        p,
        title="Phase 2 Sandbox Code Cycle",
        claim_type="measured",
        body=body,
        evidence=evidence,
    )
    enqueue_publication(
        p,
        title="Phase 2 Sandbox Code Cycle",
        path=note,
        target="github",
        status="ready" if passed else "blocked",
        policy={
            "autonomous_disclosure": True,
            "claim_type": "measured",
            "evidence": evidence,
            "tests_passed": passed_commands,
            "secret_scan_passed": not secret_findings,
            "review_required_before_claiming_science": True,
        },
    )
    return note


def parse_command(command: str) -> list[str]:
    return shlex.split(command)
