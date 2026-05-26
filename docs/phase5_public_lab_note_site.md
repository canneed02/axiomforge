# Phase 5 Public Lab-Note Site

Phase 5 turns the autonomous publication branch into a browsable public
scientific ledger.

The authoritative roadmap remains [`../PLANNING.md`](../PLANNING.md).

## Flow

```text
autonomous-publications branch
  -> read publications/manifest.json
  -> validate lab note disclosure, claim type, evidence, limitations
  -> render HTML pages for lab notes
  -> render index.html and publications/index.html
  -> write site-manifest.json
  -> verify generated pages locally
  -> commit and push as AxiomForge Autonomous System
```

## Public Surface Requirements

- Bot-authorship disclosure
- Claim type
- Evidence path
- Limitations
- Correction path
- Machine-readable manifest

## Guardrails

- The implementation branch remains separate from public artifacts.
- Markdown lab notes are not silently rewritten.
- Generated pages fail the build if required metadata is missing.
- The site is static-host compatible and includes `.nojekyll`.

Phase 5 is a public ledger, not a marketing site.
