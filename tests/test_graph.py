import tempfile
import unittest
from pathlib import Path

from build_graph import build_graph
from utils.markdown import write_note


class GraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="secondself-graph-test-", dir=".")
        self.root = Path(self.tempdir.name).resolve()
        (self.root / "wiki" / "Projects").mkdir(parents=True, exist_ok=True)
        (self.root / "wiki" / "Areas").mkdir(parents=True, exist_ok=True)
        (self.root / "data").mkdir(parents=True, exist_ok=True)

        self.note_one = self.root / "wiki" / "Projects" / "alpha-note.md"
        self.note_two = self.root / "wiki" / "Areas" / "beta-note.md"

        write_note(
            self.note_one,
            {
                "id": "note-1",
                "category": "Projects",
                "summary": "Alpha summary",
                "tags": ["alpha"],
                "links": ["note-2"],
            },
            "Alpha note body with a topic.\n",
        )
        write_note(
            self.note_two,
            {
                "id": "note-2",
                "category": "Areas",
                "summary": "Beta summary",
                "tags": ["beta"],
                "links": [],
            },
            "Beta note body with [[alpha-note]].\n",
        )

    def tearDown(self) -> None:
        try:
            self.tempdir.cleanup()
        except PermissionError:
            pass

    def test_build_graph_creates_nodes_and_edges(self) -> None:
        graph = build_graph(project_root=self.root)

        self.assertEqual(graph["meta"]["node_count"], 2)
        self.assertEqual(graph["meta"]["edge_count"], 2)
        self.assertEqual(len(graph["nodes"]), 2)
        self.assertEqual(len({node["id"] for node in graph["nodes"]}), 2)
        self.assertTrue(any(node["id"] == "note-1" for node in graph["nodes"]))
        self.assertTrue(any(edge["source"] == "note-1" and edge["target"] == "note-2" for edge in graph["edges"]))

    def test_build_graph_uses_unique_ids_for_duplicate_frontmatter_ids(self) -> None:
        duplicate_note = self.root / "wiki" / "Projects" / "gamma-note.md"
        write_note(
            duplicate_note,
            {
                "id": "note-1",
                "category": "Projects",
                "summary": "Gamma note",
                "tags": ["gamma"],
                "links": ["note-2"],
            },
            "Gamma note body.\n",
        )

        graph = build_graph(project_root=self.root)
        node_ids = [node["id"] for node in graph["nodes"]]

        self.assertEqual(node_ids.count("note-1"), 1)
        self.assertEqual(len(node_ids), 3)


if __name__ == "__main__":
    unittest.main()
