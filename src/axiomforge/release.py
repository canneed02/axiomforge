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

from .kernel import initialize, latest_review_and_replication, register_release_run
from .publisher import BOT_EMAIL, BOT_NAME, DEFAULT_PUBLICATION_BRANCH
from .site import verify_public_site


SITE_URL = "https://canneed02.github.io/axiomforge/"


@dataclass(frozen=True)
class ReleaseResult:
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
        raise ValueError(f"release repo is not a git checkout: {repo}")
    _run_git(repo, ["fetch", "origin", branch], check=False)
    checkout = _run_git(repo, ["checkout", branch], check=False)
    if checkout.returncode == 0:
        _run_git(repo, ["pull", "--ff-only", "origin", branch], check=False)
        return
    raise ValueError(f"publication branch does not exist: {branch}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _version() -> str:
    return datetime.now(timezone.utc).strftime("v%Y.%m.%d.%H%M%S.%f")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _release_gate(root: Path, repo: Path) -> tuple[bool, list[str], dict[str, Any]]:
    p = initialize(root)
    errors: list[str] = []
    site_errors = verify_public_site(repo)
    errors.extend(site_errors)

    site_manifest_path = repo / "site-manifest.json"
    publication_manifest_path = repo / "publications" / "manifest.json"
    if not site_manifest_path.exists():
        errors.append("missing site-manifest.json")
        site_manifest = {"items": []}
    else:
        site_manifest = _load_json(site_manifest_path)
    if not publication_manifest_path.exists():
        errors.append("missing publications/manifest.json")
        publication_manifest = {"items": []}
    else:
        publication_manifest = _load_json(publication_manifest_path)
    if not site_manifest.get("items"):
        errors.append("site manifest has no public items")
    for item in site_manifest.get("items", []):
        for field in ["claim_type", "evidence", "html", "markdown", "correction_path"]:
            if not item.get(field):
                errors.append(f"site item {item.get('queue_id')} missing {field}")
        for field in ["html", "markdown"]:
            rel = item.get(field)
            if rel and not (repo / rel).exists():
                errors.append(f"site item {item.get('queue_id')} missing file {rel}")

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
        "site_manifest_items": len(site_manifest.get("items", [])),
        "publication_manifest_items": len(publication_manifest.get("items", [])),
        "review": review,
        "replication": replication,
    }
    return not errors, errors, context


def _create_tarball(repo: Path, output: Path) -> None:
    with tarfile.open(output, "w:gz") as archive:
        for rel in ["index.html", "site-manifest.json", ".nojekyll"]:
            path = repo / rel
            if path.exists():
                archive.add(path, arcname=rel)
        publications = repo / "publications"
        for path in sorted(publications.rglob("*")):
            if path.is_file():
                archive.add(path, arcname=str(path.relative_to(repo)))


def build_release_candidate(root: Path, repo: Path, *, branch: str = DEFAULT_PUBLICATION_BRANCH, push: bool = True) -> ReleaseResult:
    root = root.expanduser().resolve()
    repo = repo.expanduser().resolve()
    _prepare_branch(repo, branch)
    ok, errors, context = _release_gate(root, repo)
    version = _version()
    tag = f"axiomforge-public-ledger-{version}"
    release_dir = repo / "release-candidates" / version
    release_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = release_dir / "release-manifest.json"
    tarball_path = release_dir / f"axiomforge-public-ledger-{version}.tar.gz"
    checksums_path = release_dir / "checksums.txt"

    release_manifest: dict[str, Any] = {
        "generated_by": BOT_NAME,
        "version": version,
        "tag": tag,
        "site_url": SITE_URL,
        "branch": branch,
        "status": "passed" if ok else "blocked",
        "gate_errors": errors,
        "gate_context": context,
        "artifacts": {},
        "limitations": [
            "release candidate packages public ledger artifacts only",
            "release does not claim final scientific discovery",
            "immutability is enforced by unique versioned paths and git tags",
        ],
    }
    if ok:
        _create_tarball(repo, tarball_path)
        release_manifest["artifacts"] = {
            "tarball": str(tarball_path.relative_to(repo)),
            "site_manifest": "site-manifest.json",
            "publication_manifest": "publications/manifest.json",
            "site_url": SITE_URL,
        }
    release_manifest["artifacts"]["checksums"] = str(checksums_path.relative_to(repo))
    manifest_path.write_text(json.dumps(release_manifest, indent=2, sort_keys=True) + "\n")
    checksums: list[str] = []
    for path in [manifest_path, tarball_path, repo / "site-manifest.json", repo / "publications" / "manifest.json"]:
        if path.exists():
            checksums.append(f"{_sha256(path)}  {path.relative_to(repo)}")
    checksums_path.write_text("\n".join(checksums) + "\n")

    p = initialize(root)
    register_release_run(p, version=version, status=release_manifest["status"], release=release_manifest)
    if not ok:
        return ReleaseResult(version, "blocked", str(manifest_path), tag, tuple(errors))

    _run_git(repo, ["add", "release-candidates"])
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
            ["git", "-C", str(repo), "commit", "-m", f"autonomous release candidate: {version}"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
    existing_tag = _run_git(repo, ["rev-parse", "-q", "--verify", f"refs/tags/{tag}"], check=False)
    if existing_tag.returncode == 0:
        raise ValueError(f"release tag already exists: {tag}")
    env = os.environ.copy()
    env.update({"GIT_COMMITTER_NAME": BOT_NAME, "GIT_COMMITTER_EMAIL": BOT_EMAIL})
    subprocess.run(
        ["git", "-C", str(repo), "tag", "-a", tag, "-m", f"AxiomForge public ledger release candidate {version}"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if push:
        _run_git(repo, ["push", "origin", branch])
        _run_git(repo, ["push", "origin", tag])
    return ReleaseResult(version, "passed", str(manifest_path), tag, ())
