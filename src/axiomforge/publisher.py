from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .kernel import ForgePaths, initialize, queued_publications, update_publication_status, utc_now


DEFAULT_PUBLICATION_BRANCH = "autonomous-publications"
BOT_NAME = "AxiomForge Autonomous System"
BOT_EMAIL = "axiomforge-autonomous@users.noreply.github.com"


@dataclass(frozen=True)
class PublishResult:
    queue_id: int
    status: str
    detail: dict[str, Any]


def _run_git(repo: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _secret_markers() -> tuple[re.Pattern[str], ...]:
    nvidia_marker = "".join(("n", "v", "api-"))
    generic_marker = "".join(("s", "k-"))
    return (
        re.compile(re.escape(nvidia_marker)),
        re.compile(re.escape(generic_marker) + r"[A-Za-z0-9]{20,}"),
    )


def _assert_publishable_source(p: ForgePaths, source: Path) -> Path:
    resolved = source.expanduser().resolve()
    if not resolved.exists():
        raise ValueError(f"publication source does not exist: {source}")
    if not resolved.is_file():
        raise ValueError(f"publication source is not a file: {source}")
    if not resolved.is_relative_to(p.root):
        raise ValueError(f"publication source is outside AxiomForge state: {source}")
    text = resolved.read_text(errors="replace")
    for marker in _secret_markers():
        if marker.search(text):
            raise ValueError(f"publication source failed secret scan: {source}")
    return resolved


def _prepare_publication_branch(repo: Path, branch: str) -> None:
    if not (repo / ".git").exists():
        raise ValueError(f"publication repo is not a git checkout: {repo}")
    _run_git(repo, ["fetch", "origin", branch], check=False)
    checkout = _run_git(repo, ["checkout", branch], check=False)
    if checkout.returncode == 0:
        _run_git(repo, ["pull", "--ff-only", "origin", branch], check=False)
        return
    orphan = _run_git(repo, ["checkout", "--orphan", branch], check=False)
    if orphan.returncode != 0:
        raise ValueError(orphan.stderr.strip() or f"failed to create branch {branch}")
    _run_git(repo, ["rm", "-r", "--cached", "."], check=False)
    for child in repo.iterdir():
        if child.name != ".git":
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()


def _manifest_path(repo: Path) -> Path:
    return repo / "publications" / "manifest.json"


def _load_manifest(repo: Path) -> dict[str, Any]:
    path = _manifest_path(repo)
    if not path.exists():
        return {"generated_by": BOT_NAME, "items": []}
    return json.loads(path.read_text())


def _write_manifest(repo: Path, manifest: dict[str, Any]) -> None:
    path = _manifest_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def publish_ready_queue(root: Path, repo: Path, *, branch: str = DEFAULT_PUBLICATION_BRANCH, push: bool = True) -> list[PublishResult]:
    p = initialize(root)
    repo = repo.expanduser().resolve()
    _prepare_publication_branch(repo, branch)
    results: list[PublishResult] = []

    for item in queued_publications(p, status="ready"):
        if item.target != "github":
            detail = {"reason": f"unsupported target: {item.target}"}
            update_publication_status(p, item.id, "blocked", detail)
            results.append(PublishResult(item.id, "blocked", detail))
            continue
        try:
            source = _assert_publishable_source(p, item.path)
            destination_dir = repo / "publications" / "lab-notes"
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / f"queue-{item.id:06d}-{source.name}"
            shutil.copy2(source, destination)

            manifest = _load_manifest(repo)
            manifest["updated_at"] = utc_now()
            manifest.setdefault("items", []).append(
                {
                    "queue_id": item.id,
                    "title": item.title,
                    "source": str(source),
                    "path": str(destination.relative_to(repo)),
                    "published_at": utc_now(),
                    "policy": item.policy,
                }
            )
            _write_manifest(repo, manifest)

            _run_git(repo, ["add", "publications"])
            diff = _run_git(repo, ["diff", "--cached", "--quiet"], check=False)
            if diff.returncode == 0:
                detail = {"reason": "no git changes", "branch": branch}
                update_publication_status(p, item.id, "published", detail)
                results.append(PublishResult(item.id, "published", detail))
                continue
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
                ["git", "-C", str(repo), "commit", "-m", f"autonomous publication: queue {item.id}"],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            commit = _run_git(repo, ["rev-parse", "HEAD"]).stdout.strip()
            if push:
                _run_git(repo, ["push", "origin", branch])
            detail = {"branch": branch, "commit": commit, "path": str(destination.relative_to(repo))}
            update_publication_status(p, item.id, "published", detail)
            results.append(PublishResult(item.id, "published", detail))
        except (OSError, subprocess.CalledProcessError, ValueError) as exc:
            detail = {"error": str(exc)[:1000], "branch": branch}
            update_publication_status(p, item.id, "blocked", detail)
            results.append(PublishResult(item.id, "blocked", detail))
    return results
