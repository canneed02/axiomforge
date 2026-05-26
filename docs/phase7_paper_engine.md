# Phase 7 Paper Engine

Phase 7 adds the DOI/arXiv-ready paper packaging layer.

The paper engine is not an external submission bot. It creates immutable paper
draft packages only after the public site, release artifacts, skeptic review,
replication, and evidence manifests pass.

## Command

```bash
axiomforge --root /root/axiomforge-state paper-cycle \
  --repo /root/axiomforge-publications \
  --branch autonomous-publications
```

## Generated Artifacts

Each successful run writes a versioned directory under the autonomous
publication branch:

```text
paper-drafts/<version>/
  paper.md
  paper.tex
  references.bib
  citation.cff
  doi-metadata.json
  arxiv-submission-notes.md
  submission-checklist.md
  axiomforge-paper-draft-<version>.tar.gz
  checksums.txt
  paper-manifest.json
```

The commit and annotated tag are authored by:

```text
AxiomForge Autonomous System <axiomforge-autonomous@users.noreply.github.com>
```

## Gates

The paper package is blocked if any of these conditions fail:

- no passed release run exists in the kernel registry
- the release manifest is missing, blocked, or has gate errors
- release tarball, checksums, site manifest, or publication manifest are missing
- public site verification fails
- latest skeptic review did not pass
- latest replication did not pass
- review and replication point at different subjects
- public ledger items lack title, claim type, evidence, markdown, HTML, or
  correction path

## Identity Policy

The paper engine prepares external-submission metadata, but it does not submit
to arXiv, Zenodo, Crossref, or any DOI provider.

External submission automation is only allowed later if the target provider
allows it and the system uses a bot-scoped or organization-owned identity that
clearly discloses autonomous authorship.
