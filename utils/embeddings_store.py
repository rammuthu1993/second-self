"""Embedding cache read/write helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from config import EMBEDDINGS_DIR


def text_hash(text: str) -> str:
    """Return SHA256 hex digest of text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def embedding_path(note_id: str) -> Path:
    """Return path to cached embedding JSON for a note."""
    return EMBEDDINGS_DIR / f"{note_id}.json"


def load_embedding(note_id: str) -> dict[str, Any] | None:
    """Load cached embedding for a note, or None if missing."""
    path = embedding_path(note_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_embedding(
    note_id: str,
    vector: list[float],
    model: str,
    content: str,
) -> dict[str, Any]:
    """Save embedding vector and metadata to cache."""
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "note_id": note_id,
        "model": model,
        "vector": vector,
        "text_hash": text_hash(content),
    }
    embedding_path(note_id).write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    return payload


def is_embedding_current(note_id: str, content: str, model: str) -> bool:
    """Return True if cached embedding matches content and model."""
    cached = load_embedding(note_id)
    if cached is None:
        return False
    return cached.get("text_hash") == text_hash(content) and cached.get("model") == model
