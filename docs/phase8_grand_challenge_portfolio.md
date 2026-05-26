# Phase 8 Grand Challenge Portfolio

Phase 8 adds the grand challenge portfolio and route orchestrator.

The goal is not to claim that AxiomForge has solved an open problem. The goal is
to give the autonomous system a disciplined portfolio of serious research
programs with explicit claim boundaries, verifier requirements, datasets, gates,
negative-result retention, and route execution through the existing pipeline.

## Command

Plan and ledger only:

```bash
axiomforge --root /root/axiomforge-state challenge-cycle
```

Execute the selected challenge through the full autonomous route:

```bash
axiomforge --root /root/axiomforge-state challenge-cycle \
  --repo /root/axiomforge-publications \
  --branch autonomous-publications \
  --execute-route
```

## Generated Artifacts

Each run writes a versioned directory under:

```text
/root/axiomforge-state/artifacts/challenge-runs/<timestamp>-<challenge-id>/
  portfolio.json
  selected_challenge.json
  route_plan.json
  negative_results.json
  route_result.json
  manifest.json
```

## Portfolio Fields

Every challenge contains:

- stable challenge id
- title
- objective type: `real_research` or `infrastructure_research`
- central question
- claim boundary
- verifier requirements
- dataset assumptions
- route stages
- expected evidence value
- risk
- first bounded objective
- publication gate requirements

## Route

The full route is:

```text
builder -> proof -> skeptic -> replicator -> publisher -> site -> release -> paper
```

This means a challenge may generate code and proof artifacts, but publication is
still blocked unless the skeptic and replicator gates pass. Public artifacts are
then rendered to the site, packaged as release candidates, and wrapped in a
DOI/arXiv-ready paper package without external submission.

## Negative Results

The challenge cycle writes `negative_results.json` with blocked or failed counts
from the kernel registry. Failed attempts are part of the research record. The
system must not delete them to make the public record look cleaner.

## Hard Limits

Phase 8 must not:

- claim an open problem is solved without machine-checkable or independently
  reproducible evidence
- let one agent bypass skeptic or replication gates
- hide failed attempts
- select work by hype instead of expected evidence value
- submit papers externally under a human identity
