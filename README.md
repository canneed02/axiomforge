# AxiomForge

AxiomForge is an autonomous research institution kernel.

It is designed to run continuously on a server, maintain its own research
memory, create artifacts, publish transparent autonomous lab notes, and grow into
a multi-agent scientific system.

LiveProof is not the center of AxiomForge. LiveProof is one possible research
program that AxiomForge can manage later.

## Planning

The locked planning record is [`PLANNING.md`](PLANNING.md).

If another document disagrees with `PLANNING.md`, `PLANNING.md` wins.

Roadmap status:

```text
Phase 0-8 complete
```

## Phase 0

Phase 0 creates the non-negotiable substrate:

- append-only event log
- SQLite registry
- task registry
- claim registry
- artifact registry
- local lab-note publisher
- publication policy gate
- tests
- systemd skeleton

Phase 0 does not pretend to solve major open problems. It creates the machine
that can start attacking them without losing memory, provenance, or integrity.

## Phase 1

Phase 1 turns the heartbeat into a bounded autonomous research cycle:

- redacted NVIDIA provider inventory
- optional one-call provider research memo
- machine-readable proposal artifact
- verifier artifact
- measured lab note
- GitHub publication queue item

The system can use provider keys without writing secrets to public artifacts.
External model output is treated as proposal material, not proof.

## Phase 2

Phase 2 adds the sandbox code-writing agent:

- isolated code-run workspaces
- scoped file writes
- command allowlist
- hard timeouts
- tests and compile checks
- secret scan before publication eligibility
- machine-readable diff, logs, summary, and manifest artifacts

The agent can create code artifacts without writing directly to `main`.

## Phase 3

Phase 3 adds the proof and experiment harness:

- bounded proof-run workspaces
- SymPy symbolic identity harness
- deterministic empirical experiment harness
- raw stdout/stderr/exit-code capture
- tool/version capture
- verifier artifact with `verified`, `counterexample`, or `inconclusive`
- manifest hashes

The system can measure proof and experiment infrastructure without claiming a
new theorem or broad empirical result.

## Phase 4

Phase 4 adds the reviewer and replicator gate:

- Skeptic Agent reads verifier, raw results, manifest, and policy evidence
- objections include severity and required fixes
- Replicator Agent reruns proof/experiment harnesses in a clean workspace
- replication compares verifier and harness statuses
- publication eligibility requires both review and replication pass

Failed review or replication creates follow-up work instead of hiding the
failure.

## Early Publication Capability

Autonomous publication has been implemented early as supporting infrastructure:

- `research-cycle` creates queue items
- `publish-ready` publishes only queue-approved output
- output is committed by `AxiomForge Autonomous System`
- publication uses the `autonomous-publications` branch
- code runtime stays on `main`

This was implemented before the locked roadmap reached Phase 5. It remains
supporting infrastructure for the public ledger.

## Phase 5

Phase 5 adds the public lab-note site:

- browsable `index.html`
- per-note HTML pages
- `site-manifest.json`
- correction path
- bot-authorship disclosure
- claim type, evidence, and limitations on the public surface

The site is built from the autonomous publication branch and remains separate
from implementation code.

Public site:

```text
https://canneed02.github.io/axiomforge/
```

## Phase 6

Phase 6 adds automatic release artifacts:

- release candidate directory
- release manifest
- checksums
- public ledger tarball
- bot-authored commit
- annotated git tag
- release gate using site verification, skeptic review, and replication state

The release candidate packages public ledger artifacts. It does not claim final
scientific discovery.

## Phase 7

Phase 7 adds the paper engine and DOI/arXiv-ready package pipeline:

- generated `paper.md`
- generated `paper.tex`
- bibliography metadata
- DOI metadata draft
- arXiv submission notes
- reproducibility appendix
- submission checklist
- checksums
- paper package tarball
- bot-authored commit and annotated tag
- gate using passed release, public site, skeptic review, replication, and
  evidence manifests

The paper engine prepares packages only. It does not submit to arXiv or DOI
providers under a human identity.

## Phase 8

Phase 8 adds the grand challenge portfolio and route orchestrator:

- machine-readable portfolio of serious research programs
- separation between real research objectives and infrastructure research
- explicit claim boundaries
- verifier requirements
- dataset assumptions
- expected-evidence prioritization
- negative-result ledger
- full route execution through builder, proof, skeptic, replicator, publisher,
  site, release, and paper engines

The portfolio chooses work by expected evidence value, not hype. It does not
claim that an open problem is solved unless the later evidence chain supports
that claim.

## Quickstart

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .

axiomforge --root ./state init
axiomforge --root ./state status
axiomforge --root ./state cycle --goal "bootstrap autonomous research memory"
axiomforge --root ./state research-cycle --goal "maintain autonomous research memory"
axiomforge --root ./state code-cycle --objective "maintain sandbox code-writing capability"
axiomforge --root ./state proof-cycle --objective "maintain proof and experiment harness"
axiomforge --root ./state review-cycle
axiomforge --root ./state provider-inventory
axiomforge --root ./state publish-ready --repo ./publication-repo --branch autonomous-publications
axiomforge site-build --repo ./publication-repo --branch autonomous-publications
axiomforge --root ./state release-cycle --repo ./publication-repo --branch autonomous-publications
axiomforge --root ./state paper-cycle --repo ./publication-repo --branch autonomous-publications
axiomforge --root ./state challenge-cycle --repo ./publication-repo --branch autonomous-publications --execute-route
```

## Core Rule

Autonomy is allowed. False identity is not.

Every public artifact generated by the system must disclose autonomous
generation and classify its claims as measured, replicated, hypothesis,
estimate, or speculation.
