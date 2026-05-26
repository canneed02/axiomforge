# Phase 2 Sandbox Code-Writing Agent

Phase 2 gives AxiomForge a bounded Builder Agent that can write code only inside
an isolated workspace.

The authoritative roadmap remains [`../PLANNING.md`](../PLANNING.md).

## Flow

```text
objective
  -> create artifacts/code-runs/<run>/workspace
  -> initialize a git baseline
  -> Builder Agent creates scoped code and tests
  -> run allowlisted commands with timeout
  -> secret scan the workspace
  -> write command logs, diff, summary, and manifest
  -> register artifacts and measured claim
  -> queue lab note only if gates pass
```

## Guardrails

- The workspace lives under the AxiomForge state root.
- File writes reject absolute paths and `..` path traversal.
- Commands are executed without a shell.
- Commands must match the allowlist.
- Timeouts are captured as structured command results.
- Secret scan runs before publication eligibility.
- The agent never writes directly to `main`.

## Initial Allowlist

```text
python3 -m compileall ...
python3 -m unittest ...
git diff ...
git status ...
```

## Server Runtime

`axiomforge-code.timer` runs the code cycle periodically:

```text
axiomforge code-cycle --objective "maintain sandbox code-writing capability"
```

This timer is intentionally separate from the research heartbeat and autonomous
publisher timers.
