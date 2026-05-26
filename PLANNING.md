# AxiomForge Planning

This file is the authoritative planning record for AxiomForge. If another
document disagrees with this file, this file wins.

## Project Identity

AxiomForge is independent from LiveProof.

LiveProof is only the first possible research program managed by AxiomForge. It
is not the center of the system.

```text
AxiomForge Autonomous Research Institute
```

The target is not a cron bot. The target is a transparent autonomous research
institution with durable memory, tools, code-writing ability, experiment
execution, adversarial self-review, reproduction gates, public lab notes,
release candidates, and eventually DOI/arXiv-ready scientific artifacts under a
clear bot identity.

## Prime Directive

Maximize autonomy without pretending to be human.

AxiomForge may operate continuously, write code, run experiments, critique
itself, and publish outputs. It must always disclose autonomous authorship and
must never claim a result is solved unless the evidence, reproduction, and
review gates support that claim.

## Core Architecture

```text
AxiomForge Kernel
  -> immutable event log
  -> task graph
  -> claim database
  -> artifact registry
  -> memory index
  -> policy engine
  -> publication engine
```

The system must not become one powerful agent. It must become an automatic
organization of opposing agents.

## Agent Organization

```text
Director Agent:
  selects objectives, budgets, and research portfolio priorities

Problem Scout:
  finds open problems, new papers, repos, benchmarks, and conjectures

Hypothesis Agent:
  turns ideas into testable claims

Builder Agent:
  writes code, tests, harnesses, and proof scripts

Experiment Agent:
  runs experiments, benchmarks, model evaluations, and simulations

Proof Agent:
  uses Lean, Coq, Z3, SAT, SymPy, Sage, and related tools

Skeptic Agent:
  attacks every claim, searches for overclaiming, leakage, and weak statistics

Replicator Agent:
  rebuilds from clean state, reproduces outputs, and verifies checksums

Paper Agent:
  writes papers, lab notes, tables, limitations, and appendices

Publisher Agent:
  publishes only artifacts that pass policy and reproduction gates

Feedback Agent:
  ingests issues, comments, failures, and corrections into new tasks
```

## Permission Model

Allowed:

- create repos or branches under bot identity
- write code
- run tests and CI
- run model/API calls within budget
- create artifacts
- publish lab notes automatically
- create release candidates automatically
- create paper drafts automatically
- open issues and PRs automatically

Forbidden:

- pretend to be human
- hide autonomous authorship
- claim solved without proof or reproduction
- delete negative results
- edit raw data to improve a result
- leak secrets
- publish arbitrary filesystem files

## Publication Model

The primary public channel is the system's own transparent output stream.

```text
GitHub autonomous-publications branch or static site:
  autonomous lab notes and manifests

GitHub:
  branches, release candidates, tags, issues, and PRs under bot identity

Zenodo or DOI providers:
  prepared packages first; automatic submission only if account and policy allow

arXiv and Hacker News:
  ready-to-submit artifacts first; automatic submission only if bot identity and
  platform policy allow it
```

Full autonomy is legitimate only when the public identity is explicit.

## Required Harnesses

Code:

```text
Python, optional Rust, isolated workspace, pytest, secret scan, timeouts
```

Formal:

```text
Lean, Coq, Z3, cvc5, SAT solvers, SymPy, SageMath
```

Research:

```text
paper ingestion, citation graph, claim graph, experiment registry
```

AI:

```text
NVIDIA keys, model router, budget controller, prompt/eval harness
```

Reproduction:

```text
clean clone runner, checksum, artifact manifest, secret scan
```

Publishing:

```text
static site or output branch, GitHub release builder, lab-note renderer
```

## Memory Model

```text
events.jsonl:
  append-only action log

claims.sqlite:
  claims, statuses, evidence, objections

artifacts/:
  code, data, logs, papers, proofs

knowledge_index/:
  papers, notes, and prior failures

public_ledger/:
  public outputs; no silent rewriting
```

## Initial Research Portfolio

Program 1: AI Evaluation

```text
LiveProof, benchmark decay, verifier-backed evaluations
```

Program 2: Formal Micro-Proofs

```text
theorem proving, SMT counterexamples, proof-carrying benchmarks
```

Program 3: Algorithm Discovery

```text
search for new algorithms, invariants, and optimization tricks
```

Program 4: Model Reliability Science

```text
map model failure modes across task families
```

Program 5: Autonomous Science Methodology

```text
study and improve the autonomous research system itself
```

## Autonomy Ladder

Level 1:

```text
autonomous experiment runner
```

Level 2:

```text
autonomous code writer
```

Level 3:

```text
autonomous reviewer and replicator
```

Level 4:

```text
autonomous lab-note publisher
```

Level 5:

```text
autonomous release publisher
```

Level 6:

```text
autonomous paper factory
```

Level 7:

```text
autonomous research institution with public identity
```

## Publication Law

Every public artifact must include:

- claim type: `measured`, `replicated`, `hypothesis`, `estimate`, or
  `speculation`
- evidence path
- raw data or explanation of missing raw data
- commands
- hashes when applicable
- limitations
- skeptic objections when applicable
- bot-authorship disclosure

If the artifact does not meet the gate, it can remain internal but must not be
published as a public claim.

## Locked Roadmap

Phase 0:

```text
create independent AxiomForge repository and server runtime; no LiveProof
dependency
```

Phase 1:

```text
kernel: event log, task database, artifact registry, claim database, policy
engine, local lab-note gate
```

Phase 2:

```text
sandbox code-writing agent
```

Phase 3:

```text
proof and experiment harness
```

Phase 4:

```text
reviewer and replicator multi-agent gate
```

Phase 5:

```text
public lab-note site or output stream
```

Phase 6:

```text
automatic release artifacts
```

Phase 7:

```text
paper engine and DOI/arXiv-ready pipeline
```

Phase 8:

```text
grand challenge research portfolio
```

## Current State

Completed:

- independent AxiomForge repository exists
- server runtime exists at `/root/axiomforge`
- durable state exists at `/root/axiomforge-state`
- kernel tables exist for events, tasks, claims, artifacts, publications,
  research runs, and publication queue
- NVIDIA provider router exists and uses runtime secrets only
- hourly research cycle timer is active
- autonomous publication branch exists
- publisher timer exists and publishes queued lab notes under bot identity
- Phase 2 sandbox code-writing agent exists and is deployed on the server
- code-cycle artifacts include workspace, diff, command logs, summary, and
  manifest
- `axiomforge-code.timer` runs the sandbox code-writing agent
- server smoke code-cycle passed with tests, diff artifact, command logs, and
  clean secret scan
- Phase 3 proof and experiment harness exists and is deployed on the server
- proof-cycle artifacts include bounded workspace, raw results, verifier, and
  manifest hashes
- `axiomforge-proof.timer` runs the proof and experiment harness
- server smoke proof-cycle passed with verifier status `verified`, symbolic
  status `proved`, and empirical status `replicated`
- Phase 4 reviewer and replicator gate exists and is deployed on the server
- review-cycle artifacts include skeptic review, clean replication report,
  gate decision, and manifest hashes
- `axiomforge-review.timer` runs the reviewer and replicator gate
- server smoke review-cycle passed with gate `passed`, review `passed`, and
  replication `passed`
- Phase 5 public lab-note site exists and is deployed on the server
- site-build creates `index.html`, per-note HTML pages, `.nojekyll`, and
  `site-manifest.json` on the autonomous publication branch
- `axiomforge-site.timer` runs the public site builder
- GitHub Pages is configured from `autonomous-publications` branch root
- server smoke site-build passed local verification before push

Important correction:

The autonomous publisher was implemented early. It is useful infrastructure, but
it does not redefine the roadmap. It counts as an early Phase 5 capability, not
as completion of Phase 2.

## Phase 2 Completion

Phase 2 is complete.

Phase 2 success criteria:

- create isolated workspaces for agent-written code: complete
- enforce hard timeout, file scope, and command allowlist: complete
- run tests before any output is eligible for publication: complete
- run secret scan before any artifact is registered: complete
- generate a machine-readable diff summary: complete
- store stdout, stderr, exit codes, hashes, and commands as artifacts: complete
- register code attempts as tasks and claims: complete
- block publishing if tests, secret scan, or policy gates fail: complete

Phase 2 is not allowed to:

- write directly to `main`
- publish unreviewed code as a scientific result
- run destructive shell commands
- access secrets inside generated artifacts
- skip tests to save time

The intended Phase 2 flow is:

```text
objective
  -> sandbox workspace
  -> Builder Agent writes patch
  -> tests and hygiene run
  -> diff summary artifact
  -> Skeptic pre-check
  -> claim registration
  -> local lab note
  -> publication queue only if gates pass
```

## Phase 3 Completion

Phase 3 is complete.

Phase 3 success criteria:

- create a proof/experiment run registry: complete
- support at least one symbolic harness, initially Z3 or SymPy: complete with
  SymPy
- support at least one empirical experiment harness with deterministic seeds:
  complete
- store raw stdout, stderr, commands, versions, inputs, outputs, and hashes:
  complete
- generate verifier artifacts that distinguish proof, counterexample, and
  inconclusive results: complete
- feed successful proof/experiment artifacts into Skeptic pre-checks:
  deferred to Phase 4 reviewer and replicator gate
- block publication if proof/experiment evidence is missing or inconclusive:
  complete
- keep all execution inside bounded workspaces: complete

Phase 3 is not allowed to:

- claim theorem proof without machine-checkable evidence or a clear
  counterexample-search boundary
- claim empirical results without seeds, commands, logs, and hashes
- hide inconclusive or negative results
- run unbounded solver or experiment jobs
- publish proof/experiment claims without a verifier artifact

## Phase 4 Completion

Phase 4 is complete.

Phase 4 success criteria:

- create reviewer and replication run registries: complete
- Skeptic Agent reads claims, evidence, raw logs, verifier artifacts, and
  publication policy before public eligibility: complete
- Replicator Agent reruns proof/code/experiment artifacts from a clean workspace:
  complete for proof/experiment artifacts
- reviewer output includes objections, severity, and required fixes: complete
- replication output includes commands, hashes, pass/fail status, and
  environment details: complete
- publication queue only receives `ready` status when policy, skeptic, and
  replicator gates pass: complete
- failed review or replication creates follow-up tasks rather than hiding the
  failure: complete

Phase 4 is not allowed to:

- mark a claim publishable without skeptic review
- mark a claim publishable without clean replication
- suppress reviewer objections
- overwrite raw evidence from the original run
- treat model-generated review text as proof

## Phase 5 Completion

Phase 5 is complete.

Phase 5 success criteria:

- publish a browsable public index of autonomous lab notes: complete
- expose manifest metadata for every public artifact: complete
- include bot-authorship disclosure, claim type, evidence path, limitations, and
  correction path on the public surface: complete
- make publication history append-only from the public reader perspective:
  complete
- keep implementation code separate from public artifacts: complete
- verify generated public pages locally before push: complete
- keep publication compatible with GitHub Pages or a static host: complete

Phase 5 is not allowed to:

- hide or rewrite public lab notes silently
- publish artifacts that lack claim type, evidence, or limitations
- expose runtime secrets or private environment configuration
- present autonomous output as human-authored work
- turn the public site into marketing instead of a scientific ledger

Public site:

```text
https://canneed02.github.io/axiomforge/
```

## Next Phase

The next phase is Phase 6: automatic release artifacts.

Phase 6 success criteria:

- create release candidate packages from gated public artifacts
- include checksums, manifest, raw evidence references, and generated site URL
- tag release candidates under bot identity
- create GitHub releases only when policy, site, skeptic, and replicator gates
  pass
- keep release artifacts immutable after publication
- block release creation for missing evidence, failed replication, or failed
  site verification

Phase 6 is not allowed to:

- release artifacts that did not pass policy gates
- overwrite or mutate published release assets silently
- tag arbitrary commits without artifact manifest evidence
- claim final scientific discovery from infrastructure validation alone
