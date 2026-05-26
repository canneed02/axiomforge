# Phase 1 Execution

Phase 1 upgrades AxiomForge from a bootstrap heartbeat to a bounded autonomous
research cycle.

## Runtime Loop

```text
goal
  -> provider inventory
  -> research proposal
  -> optional one-call NVIDIA memo
  -> verifier report
  -> measured claim
  -> autonomous lab note
  -> publication queue
```

## Provider Rules

Provider keys are runtime-only secrets. Public artifacts can include key
fingerprints and model names, but never raw keys.

The default mode is `offline`. Setting `AXIOMFORGE_PROVIDER_MODE=nvidia` enables
one bounded NVIDIA call per research cycle.

## Publication Rules

Phase 1 creates queue items with status `ready` or `blocked`. A ready queue item
means the artifact passed local policy and hygiene checks. It does not mean the
system has proven a scientific breakthrough.

## Completion Criteria

- `axiomforge research-cycle` produces proposal and verifier artifacts.
- `axiomforge status` includes research run and publication queue counts.
- The systemd service runs `research-cycle`, not the old bootstrap cycle.
- CI passes without committed secrets.
