"""Classify raw captures into PARA wiki notes.

Usage:
    python classify.py
    python classify.py --id <capture_id>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from config import (
    GROQ_API_KEY,
    PARA_CATEGORIES,
    RAW_DIR,
    WIKI_DIR,
    DATA_DIR,
    ensure_directories,
    validate_groq_api_key,
)
from utils.ids import generate_id, slugify, timestamp_now
from utils.markdown import read_note, write_note


def _classify_with_llm(text: str, *, fallback: str | None = None) -> dict[str, Any]:
    """Return classification data from Groq if available; otherwise use a deterministic fallback."""
    if not GROQ_API_KEY or GROQ_API_KEY == "your_key_here":
        return fallback or _fallback_classification(text)

    try:
        from groq import Groq
    except Exception:
        return fallback or _fallback_classification(text)

    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You classify notes into PARA categories. Return strict JSON with "
                        "keys: category, tags, summary."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Classify this capture. Category must be one of Projects, Areas, Resources, Archives. "
                        f"Return JSON only. Capture text:\n{text}"
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )
        payload = response.choices[0].message.content or "{}"
        parsed = json.loads(payload)
        category = str(parsed.get("category", "Resources")).strip()
        tags = parsed.get("tags") or []
        summary = str(parsed.get("summary", "Untitled capture")).strip()
        if category not in PARA_CATEGORIES:
            category = _fallback_classification(text)["category"]
        if not isinstance(tags, list):
            tags = _fallback_classification(text)["tags"]
        return {
            "category": category,
            "tags": [str(tag).strip().lower() for tag in tags if str(tag).strip()],
            "summary": summary[:120],
        }
    except Exception:
        return fallback or _fallback_classification(text)


def _fallback_classification(text: str) -> dict[str, Any]:
    """Simple heuristic fallback for classifying notes without an LLM."""
    lowered = text.lower()
    if any(word in lowered for word in ("project", "roadmap", "meeting", "launch", "plan", "milestone")):
        category = "Projects"
    elif any(word in lowered for word in ("career", "resume", "linkedin", "profile", "job", "skill")):
        category = "Areas"
    elif any(word in lowered for word in ("guide", "resource", "documentation", "docs", "article", "tutorial")):
        category = "Resources"
    else:
        category = "Archives"

    tags = []
    for keyword in ("ai", "career", "project", "learning", "notes", "resume", "meeting"):
        if keyword in lowered:
            tags.append(keyword)
    tags = tags[:5] or ["notes"]

    summary = " ".join(text.split())
    if len(summary) > 120:
        summary = summary[:117].rstrip() + "..."
    return {"category": category, "tags": tags, "summary": summary}


def _read_capture_text(raw_path: Path) -> str:
    frontmatter, body = read_note(raw_path)
    text = body.strip()
    if not text:
        text = json.dumps(frontmatter, sort_keys=True)
    return text


def _index_entry(note_path: Path, frontmatter: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": frontmatter.get("id"),
        "raw_id": frontmatter.get("raw_id"),
        "category": frontmatter.get("category"),
        "summary": frontmatter.get("summary"),
        "path": str(note_path),
        "tags": frontmatter.get("tags", []),
    }


def classify_capture(raw_path: Path, *, project_root: Path | None = None) -> Path:
    """Classify one raw capture and write a wiki note."""
    project_root = project_root or Path(__file__).resolve().parent
    os.chdir(project_root)
    ensure_directories()

    frontmatter, body = read_note(raw_path)
    capture_text = body.strip() or json.dumps(frontmatter, sort_keys=True)
    classification = _classify_with_llm(capture_text)

    category = classification["category"]
    note_id = str(frontmatter.get("id") or generate_id())
    created_at = timestamp_now()
    slug = slugify(classification.get("summary") or body.strip() or str(raw_path.stem), max_length=60)
    wiki_path = WIKI_DIR / category / f"{slug}-{note_id[:8]}.md"

    wiki_frontmatter = {
        "id": note_id,
        "raw_id": str(frontmatter.get("id") or note_id),
        "created_at": created_at,
        "updated_at": created_at,
        "category": category,
        "tags": classification.get("tags", []),
        "summary": classification.get("summary", "Untitled"),
        "links": [],
    }
    wiki_body = body.strip() + "\n"
    write_note(wiki_path, wiki_frontmatter, wiki_body)

    frontmatter["status"] = "processed"
    frontmatter["processed_at"] = created_at
    frontmatter["category"] = category
    write_note(raw_path, frontmatter, body)

    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    index_path = data_dir / "index.json"
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            index = []
    else:
        index = []

    if not any(entry.get("id") == note_id for entry in index):
        index.append(_index_entry(wiki_path, wiki_frontmatter))

    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return wiki_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify raw captures into PARA wiki notes")
    parser.add_argument("--id", dest="capture_id", help="Process a single raw capture by ID")
    args = parser.parse_args(argv)

    try:
        validate_groq_api_key()
    except ValueError:
        print("No GROQ_API_KEY found; using heuristic classification fallback.")

    ensure_directories()

    raw_files = sorted(RAW_DIR.glob("*.md"))
    if args.capture_id:
        raw_files = [path for path in raw_files if path.stem.endswith(args.capture_id) or args.capture_id in str(path)]

    if not raw_files:
        print("No raw captures found.")
        return 0

    processed = []
    for raw_path in raw_files:
        frontmatter, _ = read_note(raw_path)
        if frontmatter.get("status") == "processed":
            continue
        wiki_path = classify_capture(raw_path)
        processed.append(wiki_path)

    print(f"Processed {len(processed)} raw capture(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
