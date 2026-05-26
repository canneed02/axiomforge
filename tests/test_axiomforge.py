import tempfile
import unittest
import subprocess
import json
from pathlib import Path
from unittest import mock

from axiomforge.cli import main
from axiomforge.kernel import (
    counts,
    create_task,
    enqueue_publication,
    initialize,
    publish_lab_note,
    queued_publications,
    run_bootstrap_cycle,
)
from axiomforge.paper import build_paper_package
from axiomforge.policy import validate_lab_note
from axiomforge.providers import nvidia_inventory_from_env
from axiomforge.proof import build_verifier, run_proof_cycle
from axiomforge.publisher import publish_ready_queue
from axiomforge.research import run_phase1_research_cycle
from axiomforge.release import build_release_candidate
from axiomforge.review import build_skeptic_review, run_review_cycle
from axiomforge.sandbox import _safe_identifier, run_code_cycle, run_command, scan_for_secrets, validate_command
from axiomforge.site import build_public_site, publish_public_site


class AxiomForgeTest(unittest.TestCase):
    def test_initialize_creates_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = initialize(root)

            self.assertTrue(paths.db.exists())
            self.assertTrue(paths.events.exists())
            self.assertTrue(paths.artifacts.exists())
            self.assertTrue(paths.lab_notes.exists())
            self.assertGreaterEqual(counts(paths)["events"], 1)

    def test_create_task_records_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = initialize(Path(tmp))
            task_id = create_task(paths, "test task", "test")

            self.assertEqual(task_id, 1)
            self.assertEqual(counts(paths)["tasks"], 1)
            self.assertGreaterEqual(counts(paths)["events"], 2)

    def test_lab_note_policy_requires_disclosure_and_limitations(self):
        result = validate_lab_note(
            title="bad",
            claim_type="measured",
            body="No required language.",
            evidence="event log",
        )

        self.assertFalse(result.ok)

    def test_publish_lab_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = initialize(Path(tmp))
            out = publish_lab_note(
                paths,
                title="Test Note",
                claim_type="measured",
                evidence="events.jsonl",
                body="Autonomous generation is disclosed. Limitations: test only.",
            )

            self.assertTrue(out.exists())
            self.assertEqual(counts(paths)["publications"], 1)
            self.assertIn("AxiomForge autonomous research system", out.read_text())

    def test_lab_note_names_are_unique(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = initialize(Path(tmp))
            first = publish_lab_note(
                paths,
                title="Repeated Note",
                claim_type="measured",
                evidence="events.jsonl",
                body="Autonomous generation is disclosed. Limitations: test only.",
            )
            second = publish_lab_note(
                paths,
                title="Repeated Note",
                claim_type="measured",
                evidence="events.jsonl",
                body="Autonomous generation is disclosed. Limitations: test only.",
            )

            self.assertNotEqual(first, second)
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())

    def test_bootstrap_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_bootstrap_cycle(Path(tmp), "test bootstrap")
            paths = initialize(Path(tmp))

            self.assertTrue(out.exists())
            self.assertEqual(counts(paths)["tasks"], 1)
            self.assertEqual(counts(paths)["claims"], 1)
            self.assertEqual(counts(paths)["publications"], 1)

    def test_provider_inventory_redacts_keys(self):
        env = {
            "AXIOMFORGE_PROVIDER_MODE": "nvidia",
            "NVIDIA_API_KEY_1": "test-provider-secret",
            "AXIOMFORGE_NVIDIA_MODELS": "model-a,model-b",
        }
        with mock.patch.dict("os.environ", env, clear=True):
            inventory = nvidia_inventory_from_env().public_dict()

        self.assertTrue(inventory["enabled"])
        self.assertEqual(inventory["key_count"], 1)
        self.assertEqual(inventory["models"], ["model-a", "model-b"])
        self.assertNotIn("test-provider-secret", str(inventory))

    def test_phase1_research_cycle_queues_publication(self):
        env = {"AXIOMFORGE_PROVIDER_MODE": "offline"}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict("os.environ", env, clear=True):
            out = run_phase1_research_cycle(Path(tmp), "test autonomous science methodology")
            paths = initialize(Path(tmp))

            self.assertTrue(out.exists())
            registry_counts = counts(paths)
            self.assertEqual(registry_counts["research_runs"], 1)
            self.assertEqual(registry_counts["publication_queue"], 1)
            self.assertEqual(registry_counts["publications"], 1)
            self.assertIn("Publication Queue", out.read_text())

    def test_publish_ready_queue_commits_autonomous_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "state"
            repo = Path(tmp) / "repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init"], check=True, stdout=subprocess.PIPE)
            (repo / "README.md").write_text("runtime code should not be published\n")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.com",
                    "commit",
                    "-m",
                    "runtime branch",
                ],
                check=True,
                stdout=subprocess.PIPE,
            )
            paths = initialize(root)
            note = publish_lab_note(
                paths,
                title="Queued Note",
                claim_type="measured",
                evidence="events.jsonl",
                body="Autonomous generation is disclosed. Limitations: test only.",
            )
            queue_id = enqueue_publication(
                paths,
                title="Queued Note",
                path=note,
                target="github",
                status="ready",
                policy={"claim_type": "measured"},
            )

            results = publish_ready_queue(root, repo, push=False)

            self.assertEqual(results[0].queue_id, queue_id)
            self.assertEqual(results[0].status, "published")
            self.assertEqual(queued_publications(paths, status="ready"), [])
            self.assertEqual(len(queued_publications(paths, status="published")), 1)
            self.assertTrue((repo / "publications" / "manifest.json").exists())
            self.assertTrue(list((repo / "publications" / "lab-notes").glob("queue-*.md")))
            tree = subprocess.run(
                ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", "HEAD"],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.splitlines()
            self.assertNotIn("README.md", tree)
            self.assertTrue(all(path.startswith("publications/") for path in tree))

    def test_phase2_code_cycle_creates_gated_artifacts(self):
        env = {"AXIOMFORGE_PROVIDER_MODE": "offline"}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict("os.environ", env, clear=True):
            out = run_code_cycle(Path(tmp), "create a bounded sandbox artifact", timeout_seconds=10)
            paths = initialize(Path(tmp))

            self.assertTrue(out.exists())
            registry_counts = counts(paths)
            self.assertEqual(registry_counts["code_runs"], 1)
            self.assertEqual(registry_counts["publication_queue"], 1)
            self.assertEqual(registry_counts["publications"], 1)
            self.assertIn("Phase 2 sandbox code-writing attempt", out.read_text())
            self.assertTrue(list((Path(tmp) / "artifacts" / "code-runs").glob("*/summary.json")))
            self.assertTrue(list((Path(tmp) / "artifacts" / "code-runs").glob("*/diff.patch")))

    def test_phase2_rejects_non_allowlisted_commands(self):
        with self.assertRaises(ValueError):
            validate_command(["rm", "-rf", "/tmp/example"])

        with self.assertRaises(ValueError):
            validate_command(["python3", "-c", "print('unsafe')"])

    def test_phase2_command_timeout_is_captured(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_command(Path(tmp), ["python3", "-m", "unittest", "discover"], timeout_seconds=1)

            self.assertFalse(result.timed_out)
            self.assertIsInstance(result.exit_code, int)

    def test_phase2_secret_scan_detects_provider_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "artifact.txt").write_text("prefix " + "nv" + "api-" + "secret")

            self.assertEqual(scan_for_secrets(root), ["artifact.txt"])

    def test_phase2_sanitizes_provider_identifiers(self):
        self.assertEqual(_safe_identifier("123 bad-name", "fallback_name"), "fallback_name")
        self.assertEqual(_safe_identifier("class", "fallback_name"), "fallback_name")
        self.assertEqual(_safe_identifier("Good_Name", "fallback_name"), "good_name")

    def test_phase3_proof_cycle_creates_verifier_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_proof_cycle(Path(tmp), "validate bounded proof experiment harness", timeout_seconds=20)
            paths = initialize(Path(tmp))

            self.assertTrue(out.exists())
            registry_counts = counts(paths)
            self.assertEqual(registry_counts["proof_runs"], 1)
            self.assertEqual(registry_counts["publication_queue"], 1)
            self.assertEqual(registry_counts["publications"], 1)
            self.assertIn("Phase 3 proof/experiment cycle", out.read_text())
            verifier_paths = list((Path(tmp) / "artifacts" / "proof-runs").glob("*/verifier.json"))
            self.assertTrue(verifier_paths)
            self.assertIn('"status": "verified"', verifier_paths[0].read_text())

    def test_phase3_verifier_distinguishes_counterexample(self):
        class FakeResult:
            def __init__(self, name, status):
                self.name = name
                self.exit_code = 0
                self.timed_out = False
                self.parsed = {"status": status, "machine_checkable": True}

        verifier = build_verifier(
            "counterexample test",
            [FakeResult("symbolic", "proved"), FakeResult("empirical", "counterexample")],
        )

        self.assertEqual(verifier["status"], "counterexample")

    def test_phase4_review_cycle_requires_prior_proof_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                run_review_cycle(Path(tmp), timeout_seconds=5)

    def test_phase4_review_cycle_creates_review_and_replication_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_proof_cycle(root, "phase4 source proof", timeout_seconds=20)
            out = run_review_cycle(root, timeout_seconds=20)
            paths = initialize(root)

            self.assertTrue(out.exists())
            registry_counts = counts(paths)
            self.assertEqual(registry_counts["proof_runs"], 1)
            self.assertEqual(registry_counts["review_runs"], 1)
            self.assertEqual(registry_counts["replication_runs"], 1)
            self.assertEqual(registry_counts["publication_queue"], 2)
            self.assertIn("Phase 4 review and replication cycle", out.read_text())
            self.assertTrue(list((root / "artifacts" / "review-runs").glob("*/skeptic_review.json")))
            self.assertTrue(list((root / "artifacts" / "review-runs").glob("*/replication.json")))
            self.assertTrue(list((root / "artifacts" / "review-runs").glob("*/gate.json")))

    def test_phase4_skeptic_blocks_missing_raw_results(self):
        subject = {
            "id": 1,
            "verifier": {
                "status": "verified",
                "checks": {"has_machine_checkable_outputs": True},
                "harness_statuses": {"symbolic": "proved", "empirical": "replicated"},
                "claim_boundary": "boundary covers a test fixture",
            },
        }
        review = build_skeptic_review(subject, {"results": []}, {"hashes": {"verifier": "abc"}})

        self.assertEqual(review["status"], "blocked")
        self.assertTrue(any(objection["severity"] == "critical" for objection in review["objections"]))

    def test_phase5_builds_public_lab_note_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            note_dir = repo / "publications" / "lab-notes"
            note_dir.mkdir(parents=True)
            note = note_dir / "queue-000001-test.md"
            note.write_text(
                """# Test Note

This note was generated by the AxiomForge autonomous research system.

Claim type: `measured`

Evidence:

```text
artifact=summary.json
```

## Limitations

Test only.
"""
            )
            (repo / "publications" / "manifest.json").write_text(
                json.dumps(
                    {
                        "generated_by": "AxiomForge Autonomous System",
                        "items": [
                            {
                                "queue_id": 1,
                                "title": "Test Note",
                                "path": "publications/lab-notes/queue-000001-test.md",
                                "published_at": "2026-05-26T00:00:00Z",
                                "policy": {"claim_type": "measured"},
                            }
                        ],
                    }
                )
            )

            result = build_public_site(repo)

            self.assertEqual(result.status, "passed")
            self.assertTrue((repo / "index.html").exists())
            self.assertTrue((repo / "publications" / "lab-notes" / "queue-000001-test.html").exists())
            index = (repo / "index.html").read_text()
            note_html = (repo / "publications" / "lab-notes" / "queue-000001-test.html").read_text()
            self.assertIn("AxiomForge Autonomous System", index)
            self.assertIn("Correction path", note_html)
            self.assertIn("Claim type", note_html)
            self.assertIn("artifact=summary.json", note_html)

    def test_phase5_publish_site_commits_generated_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            remote = Path(tmp) / "remote.git"
            repo = Path(tmp) / "repo"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, stdout=subprocess.PIPE)
            subprocess.run(["git", "clone", str(remote), str(repo)], check=True, stdout=subprocess.PIPE)
            subprocess.run(["git", "-C", str(repo), "checkout", "--orphan", "autonomous-publications"], check=True, stdout=subprocess.PIPE)
            note_dir = repo / "publications" / "lab-notes"
            note_dir.mkdir(parents=True)
            (note_dir / "queue-000001-test.md").write_text(
                "# Test Note\n\n"
                "This note was generated by the AxiomForge autonomous research system.\n\n"
                "Claim type: `measured`\n\n"
                "Evidence:\n\n```text\nartifact=summary.json\n```\n\n"
                "## Limitations\n\nTest only.\n"
            )
            (repo / "publications" / "manifest.json").write_text(
                json.dumps({"generated_by": "AxiomForge Autonomous System", "items": [{"queue_id": 1, "title": "Test Note", "path": "publications/lab-notes/queue-000001-test.md"}]})
            )
            subprocess.run(["git", "-C", str(repo), "add", "publications"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "seed publications"],
                check=True,
                stdout=subprocess.PIPE,
            )
            subprocess.run(["git", "-C", str(repo), "push", "origin", "autonomous-publications"], check=True, stdout=subprocess.PIPE)

            result = publish_public_site(repo, push=False)

            self.assertEqual(result.status, "passed")
            tree = subprocess.run(
                ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", "HEAD"],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.splitlines()
            self.assertIn("index.html", tree)
            self.assertIn("site-manifest.json", tree)

    def test_phase6_release_candidate_requires_review_and_replication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "state"
            repo = Path(tmp) / "repo"
            repo.mkdir()
            (repo / ".git").mkdir()

            with self.assertRaises(ValueError):
                build_release_candidate(root, repo, push=False)

    def test_phase6_release_candidate_builds_tarball_and_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "state"
            remote = Path(tmp) / "remote.git"
            repo = Path(tmp) / "repo"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, stdout=subprocess.PIPE)
            subprocess.run(["git", "clone", str(remote), str(repo)], check=True, stdout=subprocess.PIPE)
            subprocess.run(["git", "-C", str(repo), "checkout", "--orphan", "autonomous-publications"], check=True, stdout=subprocess.PIPE)
            note_dir = repo / "publications" / "lab-notes"
            note_dir.mkdir(parents=True)
            (note_dir / "queue-000001-test.md").write_text(
                "# Test Note\n\n"
                "This note was generated by the AxiomForge autonomous research system.\n\n"
                "Claim type: `measured`\n\n"
                "Evidence:\n\n```text\nartifact=summary.json\n```\n\n"
                "## Limitations\n\nTest only.\n"
            )
            (repo / "publications" / "manifest.json").write_text(
                json.dumps({"generated_by": "AxiomForge Autonomous System", "items": [{"queue_id": 1, "title": "Test Note", "path": "publications/lab-notes/queue-000001-test.md"}]})
            )
            subprocess.run(["git", "-C", str(repo), "add", "publications"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "seed publications"],
                check=True,
                stdout=subprocess.PIPE,
            )
            subprocess.run(["git", "-C", str(repo), "push", "origin", "autonomous-publications"], check=True, stdout=subprocess.PIPE)
            publish_public_site(repo, push=False)
            run_proof_cycle(root, "phase6 source proof", timeout_seconds=20)
            run_review_cycle(root, timeout_seconds=20)

            result = build_release_candidate(root, repo, push=False)

            self.assertEqual(result.status, "passed")
            manifest = Path(result.manifest)
            self.assertTrue(manifest.exists())
            release_data = json.loads(manifest.read_text())
            tarball = repo / release_data["artifacts"]["tarball"]
            checksums = repo / release_data["artifacts"]["checksums"]
            self.assertTrue(tarball.exists())
            self.assertTrue(checksums.exists())
            self.assertIn("site_url", release_data["artifacts"])
            tag_check = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "-q", "--verify", f"refs/tags/{result.tag}"],
                check=False,
                stdout=subprocess.PIPE,
            )
            self.assertEqual(tag_check.returncode, 0)

    def test_phase7_paper_package_requires_release_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "state"
            repo = Path(tmp) / "repo"
            repo.mkdir()
            (repo / ".git").mkdir()

            with self.assertRaises(ValueError):
                build_paper_package(root, repo, push=False)

    def test_phase7_paper_package_builds_doi_arxiv_ready_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "state"
            remote = Path(tmp) / "remote.git"
            repo = Path(tmp) / "repo"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, stdout=subprocess.PIPE)
            subprocess.run(["git", "clone", str(remote), str(repo)], check=True, stdout=subprocess.PIPE)
            subprocess.run(["git", "-C", str(repo), "checkout", "--orphan", "autonomous-publications"], check=True, stdout=subprocess.PIPE)
            note_dir = repo / "publications" / "lab-notes"
            note_dir.mkdir(parents=True)
            (note_dir / "queue-000001-test.md").write_text(
                "# Test Note\n\n"
                "This note was generated by the AxiomForge autonomous research system.\n\n"
                "Claim type: `measured`\n\n"
                "Evidence:\n\n```text\nartifact=summary.json\n```\n\n"
                "## Limitations\n\nTest only.\n"
            )
            (repo / "publications" / "manifest.json").write_text(
                json.dumps({"generated_by": "AxiomForge Autonomous System", "items": [{"queue_id": 1, "title": "Test Note", "path": "publications/lab-notes/queue-000001-test.md"}]})
            )
            subprocess.run(["git", "-C", str(repo), "add", "publications"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "seed publications"],
                check=True,
                stdout=subprocess.PIPE,
            )
            subprocess.run(["git", "-C", str(repo), "push", "origin", "autonomous-publications"], check=True, stdout=subprocess.PIPE)
            publish_public_site(repo, push=False)
            run_proof_cycle(root, "phase7 source proof", timeout_seconds=20)
            run_review_cycle(root, timeout_seconds=20)
            release = build_release_candidate(root, repo, push=False)

            result = build_paper_package(root, repo, push=False)

            self.assertEqual(release.status, "passed")
            self.assertEqual(result.status, "passed")
            manifest = Path(result.manifest)
            self.assertTrue(manifest.exists())
            paper_data = json.loads(manifest.read_text())
            draft_dir = manifest.parent
            self.assertTrue((draft_dir / "paper.md").exists())
            self.assertTrue((draft_dir / "paper.tex").exists())
            self.assertTrue((draft_dir / "references.bib").exists())
            self.assertTrue((draft_dir / "doi-metadata.json").exists())
            self.assertTrue((draft_dir / "arxiv-submission-notes.md").exists())
            self.assertTrue((draft_dir / paper_data["artifacts"]["package"]).exists())
            self.assertIn("Bot-Authorship Disclosure", (draft_dir / "paper.md").read_text())
            self.assertIn("not automatically submitted", (draft_dir / "paper.tex").read_text())
            self.assertEqual(paper_data["release_tag"], release.tag)
            self.assertEqual(counts(initialize(root))["paper_runs"], 1)
            tag_check = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "-q", "--verify", f"refs/tags/{result.tag}"],
                check=False,
                stdout=subprocess.PIPE,
            )
            self.assertEqual(tag_check.returncode, 0)

    def test_cli_init(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "state"
            with mock.patch("sys.argv", ["axiomforge", "--root", str(root), "init"]):
                main()

            self.assertTrue((root / "axiomforge.db").exists())


if __name__ == "__main__":
    unittest.main()
