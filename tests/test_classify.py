import shutil
import tempfile
import unittest
from pathlib import Path

from classify import classify_capture


class ClassifyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="secondself-test-", dir=".")
        self.root = Path(self.tempdir.name).resolve()
        (self.root / "raw").mkdir(parents=True, exist_ok=True)
        (self.root / "wiki" / "Projects").mkdir(parents=True, exist_ok=True)
        (self.root / "wiki" / "Areas").mkdir(parents=True, exist_ok=True)
        (self.root / "wiki" / "Resources").mkdir(parents=True, exist_ok=True)
        (self.root / "wiki" / "Archives").mkdir(parents=True, exist_ok=True)
        (self.root / "data").mkdir(parents=True, exist_ok=True)

        self.raw_path = self.root / "raw" / "sample-note.md"
        self.raw_path.write_text(
            "---\nid: sample-id\ntype: note\nstatus: unprocessed\n---\n\nProject kickoff meeting about AI workflows.\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_classify_capture_creates_wiki_note_and_updates_raw_status(self) -> None:
        wiki_path = classify_capture(self.raw_path, project_root=self.root)

        self.assertTrue(wiki_path.exists())
        self.assertIn("wiki/", str(wiki_path))

        content = self.raw_path.read_text(encoding="utf-8")
        self.assertIn("status: processed", content)

        index_path = self.root / "data" / "index.json"
        self.assertTrue(index_path.exists())


if __name__ == "__main__":
    unittest.main()
