# Phase 6 Release Artifacts

Phase 6 packages gated public artifacts into immutable release candidates.

The authoritative roadmap remains [`../PLANNING.md`](../PLANNING.md).

## Flow

```text
autonomous-publications branch
  -> verify public site
  -> verify latest skeptic review passed
  -> verify latest replication passed
  -> create release-candidates/<version>
  -> write release-manifest.json
  -> write checksums.txt
  -> create public ledger tarball
  -> commit as AxiomForge Autonomous System
  -> tag as axiomforge-public-ledger-<version>
  -> push branch and tag
```

## Release Contents

- `release-manifest.json`
- `checksums.txt`
- public ledger tarball
- references to `site-manifest.json`
- references to `publications/manifest.json`
- public site URL
- gate context for latest skeptic review and replication

## Guardrails

- Release creation is blocked if site verification fails.
- Release creation is blocked if latest skeptic review or replication failed.
- Versioned paths and tags are unique.
- Published release artifacts are not silently mutated.
- The release candidate does not claim final scientific discovery.
