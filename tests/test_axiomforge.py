import tempfile
import unittest
from pathlib import Path
from unittest import mock

from axiomforge.cli import main
from axiomforge.kernel import counts, create_task, initialize, publish_lab_note, run_bootstrap_cycle
from axiomforge.policy import validate_lab_note


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

    def test_bootstrap_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_bootstrap_cycle(Path(tmp), "test bootstrap")
            paths = initialize(Path(tmp))

            self.assertTrue(out.exists())
            self.assertEqual(counts(paths)["tasks"], 1)
            self.assertEqual(counts(paths)["claims"], 1)
            self.assertEqual(counts(paths)["publications"], 1)

    def test_cli_init(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "state"
            with mock.patch("sys.argv", ["axiomforge", "--root", str(root), "init"]):
                main()

            self.assertTrue((root / "axiomforge.db").exists())


if __name__ == "__main__":
    unittest.main()
