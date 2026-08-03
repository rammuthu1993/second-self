import tempfile
import unittest
from pathlib import Path

from ask import ask
from utils.markdown import write_note


class AskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="secondself-ask-test-", dir=".")
        self.root = Path(self.tempdir.name).resolve()
        (self.root / "wiki" / "Projects").mkdir(parents=True, exist_ok=True)
        (self.root / "wiki" / "Areas").mkdir(parents=True, exist_ok=True)
        (self.root / "data").mkdir(parents=True, exist_ok=True)

        self.note_one = self.root / "wiki" / "Projects" / "machine-learning-note.md"
        self.note_two = self.root / "wiki" / "Areas" / "career-growth-note.md"

        write_note(
            self.note_one,
            {
                "id": "note-1",
                "category": "Projects",
                "summary": "Machine learning experiments and retrieval ideas",
                "tags": ["ai", "learning"],
                "links": [],
            },
            "This note captures experiments with retrieval pipelines and embeddings for machine learning projects.\n",
        )
        write_note(
            self.note_two,
            {
                "id": "note-2",
                "category": "Areas",
                "summary": "Career growth and mentorship notes",
                "tags": ["career"],
                "links": [],
            },
            "A note about networking and mentorship in the career growth space.\n",
        )

    def tearDown(self) -> None:
        try:
            self.tempdir.cleanup()
        except PermissionError:
            pass

    def test_ask_returns_a_grounded_answer_and_sources(self) -> None:
        result = ask("What do I know about machine learning?", project_root=self.root)

        self.assertIn("answer", result)
        self.assertIn("sources", result)
        self.assertIn("confidence", result)
        self.assertTrue(result["answer"])
        self.assertGreaterEqual(len(result["sources"]), 1)
        self.assertIn(result["confidence"], {"high", "medium", "low"})


if __name__ == "__main__":
    unittest.main()
