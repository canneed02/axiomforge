# Phase 4 Review And Replication Gate

Phase 4 prevents public eligibility until evidence has passed both a Skeptic
Agent review and a Replicator Agent clean rerun.

The authoritative roadmap remains [`../PLANNING.md`](../PLANNING.md).

## Flow

```text
latest proof_run
  -> read verifier.json, raw_results.json, manifest.json
  -> Skeptic Agent produces objections with severity and required fixes
  -> Replicator Agent copies harness scripts into a clean workspace
  -> rerun symbolic and empirical harnesses
  -> compare verifier status and harness statuses
  -> write skeptic_review.json
  -> write replication.json
  -> write gate.json
  -> queue publication only if review and replication pass
```

## Gate Status

```text
passed:
  skeptic review has no high/critical objections and replication matches

blocked:
  review or replication fails; a follow-up task is created
```

## Guardrails

- Model-generated critique is not treated as proof.
- Skeptic objections are written as artifacts, not hidden.
- Replication runs in a clean workspace.
- Original raw evidence is never overwritten.
- Publication queue receives `ready` only if both gates pass.

Phase 4 is an integrity layer, not a new result generator.
