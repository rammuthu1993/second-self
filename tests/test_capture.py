import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from capture import capture_note
from utils.markdown import read_note


class CaptureTests(unittest.TestCase):
    def test_capture_note_can_classify_into_wiki(self) -> None:
        with tempfile.TemporaryDirectory(prefix="secondself-capture-test-", dir=".") as tmp_dir:
            tmp_path = Path(tmp_dir).resolve()
            raw_dir = tmp_path / "raw"
            wiki_dir = tmp_path / "wiki"
            data_dir = tmp_path / "data"
            wiki_dir.mkdir(parents=True, exist_ok=True)
            raw_dir.mkdir(parents=True, exist_ok=True)
            data_dir.mkdir(parents=True, exist_ok=True)

            with patch("capture.RAW_DIR", raw_dir), patch("capture.ensure_directories", lambda: None), patch("classify.RAW_DIR", raw_dir), patch("classify.WIKI_DIR", wiki_dir), patch("classify.DATA_DIR", data_dir), patch("classify.ensure_directories", lambda: None), patch("classify.GROQ_API_KEY", ""):
                captured_path = capture_note("A note about machine learning", classify=True)

            self.assertTrue(captured_path.exists())
            frontmatter, _ = read_note(captured_path)
            self.assertEqual(frontmatter.get("status"), "unprocessed")

            classified_files = list((wiki_dir / "Projects").glob("*.md"))
            self.assertGreaterEqual(len(classified_files), 1)


if __name__ == "__main__":
    unittest.main()
