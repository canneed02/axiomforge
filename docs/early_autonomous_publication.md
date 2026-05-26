# Early Autonomous Publication

Autonomous publication exists as supporting infrastructure that was implemented
early. It is not the locked Phase 2.

The authoritative phase roadmap is [`../PLANNING.md`](../PLANNING.md). In that
roadmap, publication belongs to Phase 5. The next implementation phase remains:

```text
Phase 2: sandbox code-writing agent
```

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
