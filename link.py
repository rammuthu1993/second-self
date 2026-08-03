"""Create semantic links between wiki notes using embeddings."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from config import EMBEDDINGS_DIR, SIMILARITY_THRESHOLD, ensure_directories
from utils.embeddings_store import is_embedding_current, load_embedding, save_embedding
from utils.ids import slugify
from utils.markdown import read_note, write_note


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_text(note_frontmatter: dict[str, Any], note_body: str) -> str:
    summary = str(note_frontmatter.get("summary", "") or "").strip()
    tags = " ".join(str(tag) for tag in note_frontmatter.get("tags", []) or [])
    body = note_body.strip()
    return " ".join(part for part in [summary, tags, body] if part)


def _load_embedding_model() -> Any:
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    except Exception:
        return None


def _fallback_embed_texts(texts: list[str]) -> list[list[float]]:
    tokens_per_text = [Counter(re.findall(r"[a-z0-9]+", text.lower())) for text in texts]
    vocab = sorted({token for counter in tokens_per_text for token in counter.keys()})
    vectors: list[list[float]] = []
    for counter in tokens_per_text:
        vector = [counter.get(token, 0) for token in vocab]
        norm = float(np.linalg.norm(np.array(vector, dtype=float)))
        if norm:
            vector = (np.array(vector, dtype=float) / norm).tolist()
        else:
            vector = [0.0 for _ in vocab]
        vectors.append(vector)
    return vectors


def _embed_texts(model: Any, texts: list[str]) -> list[list[float]]:
    if model is None:
        return _fallback_embed_texts(texts)
    try:
        embeddings = model.encode(texts, convert_to_numpy=True)
        return [embedding.astype(float).tolist() for embedding in embeddings]
    except Exception:
        return _fallback_embed_texts(texts)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    a_vec = np.array(a, dtype=float)
    b_vec = np.array(b, dtype=float)
    if np.linalg.norm(a_vec) == 0 or np.linalg.norm(b_vec) == 0:
        return 0.0
    return float(np.dot(a_vec, b_vec) / (np.linalg.norm(a_vec) * np.linalg.norm(b_vec)))


def _existing_link_ids(frontmatter: dict[str, Any]) -> set[str]:
    links = frontmatter.get("links") or []
    if not isinstance(links, list):
        return set()
    return {str(link).strip() for link in links if str(link).strip()}


def _slug_for_note(note_path: Path) -> str:
    return slugify(note_path.stem, max_length=60)


def link_wiki_notes(*, project_root: Path | None = None, threshold: float | None = None) -> list[Path]:
    """Create semantic links for wiki notes and return the updated files."""
    project_root = project_root or Path(__file__).resolve().parent
    os.chdir(project_root)
    ensure_directories()

    threshold = threshold if threshold is not None else SIMILARITY_THRESHOLD
    wiki_root = project_root / "wiki"
    embeddings_dir = project_root / "data" / "embeddings"
    embeddings_dir.mkdir(parents=True, exist_ok=True)

    note_paths = sorted(
        [path for path in wiki_root.rglob("*.md") if path.is_file() and "raw" not in path.parts]
    )
    if len(note_paths) < 2:
        return []

    model = _load_embedding_model()
    texts: list[str] = []
    note_payloads: list[dict[str, Any]] = []
    for note_path in note_paths:
        frontmatter, body = read_note(note_path)
        text = _build_text(frontmatter, body)
        note_payloads.append({"path": note_path, "frontmatter": frontmatter, "body": body, "text": text})
        texts.append(text)

    vectors = _embed_texts(model, texts)

    for index, payload in enumerate(note_payloads):
        note_id = str(payload["frontmatter"].get("id") or payload["path"].stem)
        content_text = payload["text"]
        if not is_embedding_current(note_id, content_text, "sentence-transformers/all-MiniLM-L6-v2", embeddings_dir):
            save_embedding(note_id, vectors[index], "sentence-transformers/all-MiniLM-L6-v2", content_text, embeddings_dir)

    updated_paths: list[Path] = []
    for i, left in enumerate(note_payloads):
        left_frontmatter = left["frontmatter"]
        left_id = str(left_frontmatter.get("id") or left["path"].stem)
        left_payload = load_embedding(left_id, embeddings_dir) or {}
        left_vector = left_payload.get("vector") or []
        if not left_vector:
            continue

        left_existing = _existing_link_ids(left_frontmatter)
        left_body = left["body"]
        for j, right in enumerate(note_payloads):
            if i == j:
                continue
            right_frontmatter = right["frontmatter"]
            right_id = str(right_frontmatter.get("id") or right["path"].stem)
            right_payload = load_embedding(right_id, embeddings_dir) or {}
            right_vector = right_payload.get("vector") or []
            if not right_vector:
                continue

            score = _cosine_similarity(left_vector, right_vector)
            if score < threshold:
                continue

            if right_id in left_existing:
                continue

            left_existing.add(right_id)
            right_existing = _existing_link_ids(right_frontmatter)
            if left_id not in right_existing:
                right_existing.add(left_id)

            left_frontmatter["links"] = sorted(left_existing)
            right_frontmatter["links"] = sorted(right_existing)

            left_slug = _slug_for_note(left["path"])
            right_slug = _slug_for_note(right["path"])
            left_body = left_body.rstrip() + f"\n\n[[{right_slug}]]"
            if not re.search(rf"\[\[{re.escape(right_slug)}\]\]", right["body"]):
                right_body = right["body"].rstrip() + f"\n\n[[{left_slug}]]"
            else:
                right_body = right["body"]

            left["frontmatter"] = left_frontmatter
            right["frontmatter"] = right_frontmatter
            left["body"] = left_body
            right["body"] = right_body

            note_payloads[j]["frontmatter"] = right_frontmatter
            note_payloads[j]["body"] = right_body

        if left["body"] != note_payloads[i]["body"]:
            note_payloads[i]["body"] = left["body"]

        if left["frontmatter"] != note_payloads[i]["frontmatter"]:
            note_payloads[i]["frontmatter"] = left_frontmatter

    for payload in note_payloads:
        note_path = payload["path"]
        frontmatter = payload["frontmatter"]
        body = payload["body"]
        write_note(note_path, frontmatter, body)
        updated_paths.append(note_path)

    return sorted(set(updated_paths))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Link wiki notes using semantic similarity")
    parser.add_argument("--threshold", type=float, default=SIMILARITY_THRESHOLD, help="Similarity threshold")
    args = parser.parse_args(argv)

    updated = link_wiki_notes(threshold=args.threshold)
    print(f"Linked {len(updated)} wiki note(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
