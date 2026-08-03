"""Build a graph.json representation of PARA wiki notes and their links."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ensure_directories
from utils.markdown import read_note


def _clean_text(value: str | None) -> str:
    return (value or "").strip()


def _extract_preview(body: str, summary: str | None) -> str:
    if summary:
        return summary.strip()

    candidate = "\n".join(line.strip() for line in body.splitlines() if line.strip())
    if not candidate:
        return ""
    return candidate[:180]


def _extract_body_links(body: str) -> list[str]:
    return [match.group(1).strip() for match in re.finditer(r"\[\[([^\]]+)\]\]", body)]


def build_graph(*, project_root: Path | None = None) -> dict[str, Any]:
    """Parse wiki notes and return a graph payload with nodes and edges."""
    project_root = project_root or Path(__file__).resolve().parent
    ensure_directories()

    wiki_root = project_root / "wiki"
    data_dir = project_root / "data"
    graph_path = data_dir / "graph.json"
    data_dir.mkdir(parents=True, exist_ok=True)

    note_paths = sorted([path for path in wiki_root.rglob("*.md") if path.is_file()])
    nodes: list[dict[str, Any]] = []
    node_lookup: dict[str, dict[str, Any]] = {}

    for note_path in note_paths:
        frontmatter, body = read_note(note_path)
        raw_id = str(frontmatter.get("id") or note_path.stem)
        category = str(frontmatter.get("category") or note_path.parent.name)
        summary = _clean_text(frontmatter.get("summary"))
        tags = frontmatter.get("tags") or []
        slug = note_path.stem
        preview = _extract_preview(body, summary)

        note_id = raw_id
        if note_id in node_lookup:
            note_id = f"{raw_id}-{slug}"
        if note_id in node_lookup:
            note_id = f"{raw_id}-{len(nodes) + 1}"

        node = {
            "id": note_id,
            "slug": slug,
            "label": summary or slug.replace("-", " ").title(),
            "category": category,
            "tags": [str(tag) for tag in tags if str(tag).strip()],
            "path": str(note_path.relative_to(project_root)).replace("\\", "/"),
            "summary": summary,
            "preview": preview,
        }
        nodes.append(node)
        node_lookup[note_id] = node
        node_lookup[raw_id] = node
        node_lookup[slug] = node

    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str]] = set()

    for node in nodes:
        linked_targets: set[str] = set()
        frontmatter_links = frontmatter = {}
        note_path = project_root / node["path"]
        frontmatter, body = read_note(note_path)
        frontmatter_links = frontmatter.get("links") or []
        for raw_link in frontmatter_links:
            target = str(raw_link).strip()
            if not target:
                continue
            linked_targets.add(target)

        for wiki_link in _extract_body_links(body):
            linked_targets.add(wiki_link)

        for target in sorted(linked_targets):
            resolved_target = node_lookup.get(target)
            if not resolved_target:
                continue
            if node["id"] == resolved_target["id"]:
                continue
            edge_key = (node["id"], resolved_target["id"])
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            edges.append(
                {
                    "id": f"{node['id']}-{resolved_target['id']}",
                    "source": node["id"],
                    "target": resolved_target["id"],
                    "type": "explicit",
                }
            )

    graph = {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "source": "build_graph.py",
        },
    }
    graph_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    return graph


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build graph.json from wiki notes")
    args = parser.parse_args(argv)
    graph = build_graph()
    print(f"Wrote {graph['meta']['node_count']} node(s) and {graph['meta']['edge_count']} edge(s) to data/graph.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
