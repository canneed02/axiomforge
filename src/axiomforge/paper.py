from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .kernel import initialize, latest_release_run, latest_review_and_replication, register_paper_run
from .publisher import BOT_EMAIL, BOT_NAME, DEFAULT_PUBLICATION_BRANCH
from .release import SITE_URL
from .site import verify_public_site


@dataclass(frozen=True)
class PaperResult:
    version: str
    status: str
    manifest: str
    tag: str
    errors: tuple[str, ...]


def _run_git(repo: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _prepare_branch(repo: Path, branch: str) -> None:
    if not (repo / ".git").exists():
        raise ValueError(f"paper repo is not a git checkout: {repo}")
    _run_git(repo, ["fetch", "origin", branch], check=False)
    checkout = _run_git(repo, ["checkout", branch], check=False)
    if checkout.returncode == 0:
        _run_git(repo, ["pull", "--ff-only", "origin", branch], check=False)
        return
    raise ValueError(f"publication branch does not exist: {branch}")


def _version() -> str:
    return datetime.now(timezone.utc).strftime("v%Y.%m.%d.%H%M%S.%f")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _escape_table(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "\\|")


def _escape_tex(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in value)


def _paper_gate(root: Path, repo: Path) -> tuple[bool, list[str], dict[str, Any]]:
    p = initialize(root)
    errors: list[str] = []
    errors.extend(verify_public_site(repo))

    release = latest_release_run(p, status="passed")
    if not release:
        errors.append("missing passed release run")
        release_payload: dict[str, Any] = {}
    else:
        release_payload = release["payload"]

    site_manifest_path = repo / "site-manifest.json"
    if site_manifest_path.exists():
        site_manifest = _load_json(site_manifest_path)
    else:
        site_manifest = {"items": []}
        errors.append("missing site-manifest.json")

    items = site_manifest.get("items", [])
    if not items:
        errors.append("site manifest has no public items")
    for item in items:
        for field in ["title", "claim_type", "evidence", "html", "markdown", "correction_path"]:
            if not item.get(field):
                errors.append(f"site item {item.get('queue_id')} missing {field}")

    release_version = str(release_payload.get("version", ""))
    release_dir = repo / "release-candidates" / release_version if release_version else repo / "release-candidates" / "missing"
    release_manifest_path = release_dir / "release-manifest.json"
    if not release_manifest_path.exists():
        errors.append("missing release manifest file")
        release_manifest: dict[str, Any] = {}
    else:
        release_manifest = _load_json(release_manifest_path)
    if release_manifest.get("status") != "passed":
        errors.append("release manifest is not passed")
    if release_manifest.get("gate_errors"):
        errors.append("release manifest contains gate errors")
    artifacts = release_manifest.get("artifacts", {})
    for key in ["tarball", "checksums", "site_manifest", "publication_manifest"]:
        rel = artifacts.get(key)
        if not rel:
            errors.append(f"release manifest missing artifact {key}")
        elif not (repo / rel).exists():
            errors.append(f"release artifact missing file {rel}")

    gates = latest_review_and_replication(p)
    review = gates["review"]
    replication = gates["replication"]
    if not review or review["status"] != "passed":
        errors.append("latest skeptic review did not pass")
    if not replication or replication["status"] != "passed":
        errors.append("latest replication did not pass")
    if review and replication and review["subject_id"] != replication["subject_id"]:
        errors.append("latest review and replication subjects differ")

    context = {
        "release": release,
        "release_manifest": release_manifest,
        "review": review,
        "replication": replication,
        "site_items": items,
    }
    return not errors, errors, context


def _evidence_table(items: list[dict[str, Any]]) -> str:
    rows = ["| Public item | Claim type | Evidence | Ledger paths |", "| --- | --- | --- | --- |"]
    for item in items:
        paths = f"{item.get('markdown', '')}; {item.get('html', '')}"
        rows.append(
            "| "
            + " | ".join(
                [
                    _escape_table(item.get("title", "")),
                    _escape_table(item.get("claim_type", "")),
                    _escape_table(item.get("evidence", "")),
                    _escape_table(paths),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def _paper_markdown(version: str, context: dict[str, Any]) -> str:
    release_manifest = context["release_manifest"]
    release = context["release"]
    review = context["review"]
    replication = context["replication"]
    items = context["site_items"]
    release_version = release_manifest.get("version", release.get("version", "unknown") if release else "unknown")
    release_tag = release_manifest.get("tag", "unknown")
    return f"""# AxiomForge Autonomous Research Ledger: Verifier-Gated Publication Pipeline Report {version}

## Bot-Authorship Disclosure

This draft was generated by the AxiomForge Autonomous System. It is an
autonomous research artifact, not a human-authored scientific submission. It is
prepared for DOI/arXiv-style packaging only when the release, public site,
skeptic review, replication, and evidence-manifest gates pass.

## Abstract

This report describes the current AxiomForge autonomous research publication
pipeline as a measured infrastructure artifact. The pipeline maintains an
append-only event log, public lab-note ledger, site manifest, release candidate,
checksums, skeptic review gate, replication gate, and immutable paper package.
The result is not a claim of a new theorem or solved scientific problem. It is
a reproducible packaging record for autonomous research outputs that have passed
the current internal gates.

## Method

The paper engine reads the latest passed release run from the AxiomForge kernel
registry, verifies the public site, verifies the release manifest and artifact
files, checks that the latest skeptic review and replication runs passed, and
then materializes this draft with metadata, bibliography, reproducibility
appendix, checksums, and a submission checklist.

## Evidence Table

{_evidence_table(items)}

## Artifact Manifest References

- Public site: {SITE_URL}
- Release version: `{release_version}`
- Release tag: `{release_tag}`
- Release manifest: `release-candidates/{release_version}/release-manifest.json`
- Release run id: `{release.get("id") if release else "unknown"}`
- Skeptic review id: `{review.get("id") if review else "unknown"}`
- Replication id: `{replication.get("id") if replication else "unknown"}`

## Reproducibility Appendix

1. Clone the public ledger branch.
2. Check out tag `{release_tag}`.
3. Verify `release-candidates/{release_version}/checksums.txt`.
4. Open `site-manifest.json` and confirm every public item has claim type,
   evidence, source markdown, HTML, and correction path.
5. Inspect the release manifest gate context for review and replication status.
6. Treat this paper draft as generated infrastructure evidence, not as a final
   human-submitted paper.

## Limitations

- The draft is generated from public ledger artifacts and kernel registry state.
- The package does not submit itself to arXiv, Zenodo, Crossref, or any DOI
  provider.
- The package does not claim scientific novelty from infrastructure validation.
- The current evidence table reflects available public lab notes, not the full
  space of possible autonomous research outputs.
- Human operators must use a bot-scoped public identity if they later enable
  external submission automation.

## Ethics and Identity

AxiomForge must not impersonate a human researcher. Any later external
submission must disclose autonomous authorship and use provider policies that
allow automated or organization-owned submission identities.
"""


def _paper_tex(markdown_title: str, version: str, context: dict[str, Any]) -> str:
    release_manifest = context["release_manifest"]
    items = context["site_items"]
    rows = "\n".join(
        f"{_escape_tex(str(item.get('title', '')))} & {_escape_tex(str(item.get('claim_type', '')))} & {_escape_tex(str(item.get('html', '')))} \\\\"
        for item in items
    )
    return rf"""\documentclass[11pt]{{article}}
\usepackage[margin=1in]{{geometry}}
\usepackage{{hyperref}}
\usepackage{{longtable}}
\title{{{_escape_tex(markdown_title)}}}
\author{{AxiomForge Autonomous System}}
\date{{{_escape_tex(version)}}}
\begin{{document}}
\maketitle

\section*{{Bot-Authorship Disclosure}}
This draft was generated by the AxiomForge Autonomous System. It is prepared as
a DOI/arXiv-ready package artifact and is not automatically submitted under a
human identity.

\section*{{Abstract}}
This report describes the AxiomForge autonomous research publication pipeline
as a measured infrastructure artifact. It references the public ledger,
release candidate, checksum manifest, skeptic review gate, and replication gate.
It does not claim a new theorem or solved scientific problem.

\section*{{Method}}
The paper engine reads the latest passed release run, verifies public site
metadata, verifies release artifacts, and checks the latest skeptic review and
replication records before producing this draft package.

\section*{{Evidence Table}}
\begin{{longtable}}{{p{{0.42\linewidth}}p{{0.16\linewidth}}p{{0.30\linewidth}}}}
Public item & Claim type & Ledger path \\
\hline
{rows}
\end{{longtable}}

\section*{{Artifact Manifest References}}
Public site: \url{{{SITE_URL}}}. Release tag:
\texttt{{{_escape_tex(str(release_manifest.get("tag", "unknown")))}}}.
Release manifest:
\texttt{{release-candidates/{_escape_tex(str(release_manifest.get("version", "unknown")))}/release-manifest.json}}.

\section*{{Limitations}}
This package does not submit itself to arXiv or DOI providers, does not
impersonate a human author, and does not claim scientific novelty from
infrastructure validation alone.

\bibliographystyle{{plain}}
\bibliography{{references}}
\end{{document}}
"""


def _write_support_files(draft_dir: Path, version: str, context: dict[str, Any]) -> dict[str, str]:
    release_manifest = context["release_manifest"]
    release_version = str(release_manifest.get("version", "unknown"))
    title = f"AxiomForge Autonomous Research Ledger: Verifier-Gated Publication Pipeline Report {version}"
    files = {
        "paper.md": _paper_markdown(version, context),
        "paper.tex": _paper_tex(title, version, context),
        "references.bib": f"""@misc{{axiomforge_public_ledger_{release_version.replace('.', '_')},
  title = {{AxiomForge Public Research Ledger}},
  author = {{{BOT_NAME}}},
  year = {{2026}},
  howpublished = {{\\url{{{SITE_URL}}}}},
  note = {{Autonomous public ledger release {release_version}}}
}}
""",
        "citation.cff": f"""cff-version: 1.2.0
message: "If this autonomous artifact informs your work, cite the public ledger package."
title: "AxiomForge autonomous research ledger paper draft {version}"
authors:
  - name: "{BOT_NAME}"
version: "{version}"
date-released: "{datetime.now(timezone.utc).date().isoformat()}"
url: "{SITE_URL}"
""",
        "doi-metadata.json": json.dumps(
            {
                "generated_by": BOT_NAME,
                "title": title,
                "version": version,
                "creators": [{"name": BOT_NAME, "type": "Organizational"}],
                "related_identifiers": [
                    {"relation": "documents", "identifier": SITE_URL, "scheme": "url"},
                    {"relation": "isSupplementTo", "identifier": str(release_manifest.get("tag", "")), "scheme": "git-tag"},
                ],
                "submission_policy": "prepared only; external DOI submission requires a bot-scoped identity and provider approval",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "arxiv-submission-notes.md": f"""# arXiv Submission Notes

This package is arXiv-ready in structure but must not be submitted under a
human identity by automation.

- Authorship disclosure: `{BOT_NAME}`
- Source TeX: `paper.tex`
- Bibliography: `references.bib`
- Release tag: `{release_manifest.get("tag", "unknown")}`
- Public site: {SITE_URL}
- Required human/bot-operator check: confirm arXiv policy and identity before
  any external submission.
""",
        "submission-checklist.md": """# Submission Checklist

- [x] Bot-authorship disclosure included.
- [x] Abstract included.
- [x] Method included.
- [x] Evidence table included.
- [x] Limitations included.
- [x] Reproducibility appendix included.
- [x] Release artifact manifest references included.
- [x] Bibliography metadata prepared.
- [ ] External submission identity approved by target provider.
- [ ] Human impersonation risk reviewed.
""",
    }
    for name, content in files.items():
        (draft_dir / name).write_text(content)
    return {name: name for name in files}


def _create_tarball(draft_dir: Path, output: Path, members: list[str]) -> None:
    with tarfile.open(output, "w:gz") as archive:
        for rel in members:
            archive.add(draft_dir / rel, arcname=rel)


def build_paper_package(root: Path, repo: Path, *, branch: str = DEFAULT_PUBLICATION_BRANCH, push: bool = True) -> PaperResult:
    root = root.expanduser().resolve()
    repo = repo.expanduser().resolve()
    _prepare_branch(repo, branch)
    ok, errors, context = _paper_gate(root, repo)
    version = _version()
    tag = f"axiomforge-paper-draft-{version}"
    draft_dir = repo / "paper-drafts" / version
    draft_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = draft_dir / "paper-manifest.json"
    checksums_path = draft_dir / "checksums.txt"
    tarball_path = draft_dir / f"axiomforge-paper-draft-{version}.tar.gz"

    artifacts: dict[str, str] = {}
    if ok:
        artifacts.update(_write_support_files(draft_dir, version, context))
        artifacts["package"] = tarball_path.name
        _create_tarball(draft_dir, tarball_path, [name for name in artifacts if name != "package"])
    artifacts["checksums"] = checksums_path.name

    release_manifest = context.get("release_manifest", {})
    paper_manifest: dict[str, Any] = {
        "generated_by": BOT_NAME,
        "version": version,
        "tag": tag,
        "branch": branch,
        "status": "passed" if ok else "blocked",
        "gate_errors": errors,
        "site_url": SITE_URL,
        "release_version": release_manifest.get("version"),
        "release_tag": release_manifest.get("tag"),
        "artifacts": artifacts,
        "limitations": [
            "paper package is prepared, not externally submitted",
            "bot authorship must remain disclosed",
            "infrastructure validation is not a scientific novelty claim",
        ],
    }
    manifest_path.write_text(json.dumps(paper_manifest, indent=2, sort_keys=True) + "\n")
    checksum_targets = [manifest_path, *[draft_dir / rel for key, rel in artifacts.items() if key != "checksums"]]
    checksums = [f"{_sha256(path)}  {path.relative_to(repo)}" for path in checksum_targets if path.exists()]
    checksums_path.write_text("\n".join(checksums) + "\n")

    p = initialize(root)
    register_paper_run(p, version=version, status=paper_manifest["status"], paper=paper_manifest)
    if not ok:
        return PaperResult(version, "blocked", str(manifest_path), tag, tuple(errors))

    _run_git(repo, ["add", "paper-drafts"])
    diff = _run_git(repo, ["diff", "--cached", "--quiet"], check=False)
    if diff.returncode != 0:
        env = os.environ.copy()
        env.update(
            {
                "GIT_AUTHOR_NAME": BOT_NAME,
                "GIT_AUTHOR_EMAIL": BOT_EMAIL,
                "GIT_COMMITTER_NAME": BOT_NAME,
                "GIT_COMMITTER_EMAIL": BOT_EMAIL,
            }
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", f"autonomous paper draft: {version}"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
    existing_tag = _run_git(repo, ["rev-parse", "-q", "--verify", f"refs/tags/{tag}"], check=False)
    if existing_tag.returncode == 0:
        raise ValueError(f"paper tag already exists: {tag}")
    env = os.environ.copy()
    env.update({"GIT_COMMITTER_NAME": BOT_NAME, "GIT_COMMITTER_EMAIL": BOT_EMAIL})
    subprocess.run(
        ["git", "-C", str(repo), "tag", "-a", tag, "-m", f"AxiomForge DOI/arXiv-ready paper draft {version}"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if push:
        _run_git(repo, ["push", "origin", branch])
        _run_git(repo, ["push", "origin", tag])
    return PaperResult(version, "passed", str(manifest_path), tag, ())
