import tempfile
import unittest
from pathlib import Path

from link import link_wiki_notes
from utils.markdown import write_note


class LinkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="secondself-link-test-", dir=".")
        self.root = Path(self.tempdir.name).resolve()
        (self.root / "wiki" / "Projects").mkdir(parents=True, exist_ok=True)
        (self.root / "wiki" / "Areas").mkdir(parents=True, exist_ok=True)
        (self.root / "data" / "embeddings").mkdir(parents=True, exist_ok=True)

        self.note_one = self.root / "wiki" / "Projects" / "ai-ml-note-1.md"
        self.note_two = self.root / "wiki" / "Projects" / "ai-ml-note-2.md"

        write_note(
            self.note_one,
            {
                "id": "note-1",
                "category": "Projects",
                "summary": "Machine learning workflow notes",
                "tags": ["ai", "learning"],
                "links": [],
            },
            "We are discussing machine learning pipelines and model evaluation.\n",
        )
        write_note(
            self.note_two,
            {
                "id": "note-2",
                "category": "Projects",
                "summary": "Machine learning experiments",
                "tags": ["ai", "experiments"],
                "links": [],
            },
            "We are studying machine learning experiments and training data.\n",
        )

    def tearDown(self) -> None:
        try:
            self.tempdir.cleanup()
        except PermissionError:
            pass

    def test_link_wiki_notes_creates_embeddings_and_links(self) -> None:
        linked_paths = link_wiki_notes(project_root=self.root, threshold=0.1)

        self.assertEqual(len(linked_paths), 2)
        note_one_content = self.note_one.read_text(encoding="utf-8")
        note_two_content = self.note_two.read_text(encoding="utf-8")

        self.assertIn("[[ai-ml-note-2]]", note_one_content)
        self.assertIn("[[ai-ml-note-1]]", note_two_content)

        embedding_dir = self.root / "data" / "embeddings"
        self.assertTrue(any(embedding_dir.glob("*.json")))


if __name__ == "__main__":
    unittest.main()
