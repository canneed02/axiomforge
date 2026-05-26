# Phase 3 Proof And Experiment Harness

Phase 3 gives AxiomForge bounded proof and experiment execution.

The authoritative roadmap remains [`../PLANNING.md`](../PLANNING.md).

## Flow

```text
objective
  -> create artifacts/proof-runs/<run>/workspace
  -> write symbolic and empirical harness scripts
  -> run scripts without shell
  -> capture stdout, stderr, exit code, timeout, versions, and parsed JSON
  -> write raw_results.json
  -> write verifier.json
  -> write manifest.json with hashes
  -> register proof run, artifacts, measured claim, and lab note
  -> queue publication only if verifier status is verified
```

## Initial Harnesses

Symbolic:

```text
SymPy polynomial identity check
```

Empirical:

```text
Python deterministic seeded sort invariant check
```

## Verifier Status

```text
verified:
  symbolic harness proved and empirical harness replicated

counterexample:
  any harness finds a counterexample

inconclusive:
  timeout, command failure, parse failure, or missing evidence
```

## Guardrails

- Execution stays inside the proof-run workspace.
- Commands run without a shell.
- Timeouts are captured as structured evidence.
- Raw outputs and hashes are retained.
- No proof or empirical claim can be published without `verifier.json`.
- The cycle does not claim a new theorem or universal empirical truth.
