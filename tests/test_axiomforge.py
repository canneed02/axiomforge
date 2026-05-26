import tempfile
import unittest
from pathlib import Path
from unittest import mock

from axiomforge.cli import main
from axiomforge.kernel import counts, create_task, initialize, publish_lab_note, run_bootstrap_cycle
from axiomforge.policy import validate_lab_note
from axiomforge.providers import nvidia_inventory_from_env
from axiomforge.research import run_phase1_research_cycle


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

    def test_cli_init(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "state"
            with mock.patch("sys.argv", ["axiomforge", "--root", str(root), "init"]):
                main()

            self.assertTrue((root / "axiomforge.db").exists())


if __name__ == "__main__":
    unittest.main()
