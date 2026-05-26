# Phase 2 Autonomous Publication

Phase 2 makes AxiomForge publish its own approved outputs instead of relying on
manual posting.

## Separation

Implementation code stays on `main`.

Autonomous outputs are pushed to `autonomous-publications` from a separate
server checkout:

```text
/root/axiomforge              -> runtime code, main
/root/axiomforge-publications -> autonomous output branch
```

## Publication Flow

```text
research-cycle
  -> publication_queue(status=ready)
  -> publish-ready
  -> secret scan
  -> copy lab note to publications/lab-notes
  -> update publications/manifest.json
  -> commit as AxiomForge Autonomous System
  -> push autonomous-publications
  -> mark queue item published
```

## Guardrails

- The source artifact must live inside the AxiomForge state root.
- The source artifact must be a regular file.
- The source artifact must pass secret scanning.
- Unsupported targets are blocked.
- Failed git operations mark the queue item blocked.

This is autonomous publication of outputs, not automatic rewriting of the
runtime codebase.
