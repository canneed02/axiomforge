# AxiomForge Master Plan

## Mission

AxiomForge is an autonomous research institution: a server-resident system that
can discover problems, create hypotheses, write code, run experiments, verify
artifacts, publish transparent lab notes, and accumulate scientific memory.

The project is independent from LiveProof. LiveProof can become one research
program inside AxiomForge, but AxiomForge is the larger institution.

## Prime Directive

Produce reproducible scientific artifacts with explicit autonomous identity.

Autonomy is mandatory. Fraud is forbidden.

## Target Shape

```text
AxiomForge Kernel
  -> event log
  -> SQLite registry
  -> claim graph
  -> artifact registry
  -> policy engine
  -> publication engine
  -> scheduler
  -> tool harness
  -> agent runtime
```

## Research Programs

Initial portfolio:

1. AI evaluation and benchmark decay
2. theorem proving and formal micro-proofs
3. algorithm discovery
4. model reliability science
5. autonomous science methodology

## Agent Roles

Director:
selects research objectives and budget.

Scout:
finds candidate problems and prior work.

Hypothesis:
turns ideas into testable claims.

Builder:
writes code, tests, harnesses, and proof scripts.

Experimenter:
runs simulations, model calls, and benchmarks.

Proof:
uses formal or symbolic tools when possible.

Skeptic:
attacks every claim and searches for confounders.

Replicator:
rebuilds from clean state and verifies checksums.

Publisher:
publishes lab notes and release candidates through policy gates.

Feedback:
ingests public issues, comments, failures, and corrections.

## Autonomy Ladder

Level 0:
kernel, memory, policy, local publication.

Level 1:
scheduled autonomous heartbeat and lab notes.

Level 2:
code-writing in isolated branches with tests.

Level 3:
multi-agent review, skeptic, and replication.

Level 4:
automatic public lab-note publication under bot identity.

Level 5:
automatic release candidates and DOI-ready artifacts.

Level 6:
paper drafts and arXiv-ready packages.

Level 7:
full public autonomous research institution.

## Publication Policy

Public notes are allowed if they are transparent.

Every public artifact must include:

- autonomous authorship disclosure
- claim classification
- evidence path
- raw artifacts or explanation
- limitations
- correction path

Claim types:

```text
measured
replicated
hypothesis
estimate
speculation
```

Forbidden:

- pretending to be human
- claiming solved without proof or reproduction
- hiding failed replications
- editing raw data to improve a claim
- leaking secrets

## Phase 0 Definition

Phase 0 is complete when AxiomForge can:

- initialize state
- append events
- register tasks
- register claims
- register artifacts
- publish a local lab note through policy gates
- run tests
- deploy to server with systemd skeleton

Phase 0 is not allowed to:

- submit arXiv
- post Hacker News
- create external releases
- claim it solved an open problem

## Phase 1 Definition

Phase 1 is complete when AxiomForge can:

- read provider configuration without exposing secrets
- run a bounded autonomous research cycle
- create proposal and verifier artifacts
- classify the selected research program
- publish a measured local lab note
- enqueue the note for GitHub publication
- run unattended through systemd

Phase 1 is not allowed to:

- push unreviewed claims directly to a public branch
- spend unbounded provider quota
- treat model output as proof
- publish secrets, private prompts, or raw credentials

## First Serious Target After Phase 1

Build the autonomous code-writing harness:

```text
objective -> branch -> code diff -> tests -> skeptic review -> local lab note
```

No code-writing autonomy should run without:

- sandboxed workspace
- hard timeout
- secret scan
- tests
- diff summary
- rollback path
