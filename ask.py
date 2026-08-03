"""Retrieval-augmented question answering over the local wiki notes."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from config import (
    EMBEDDINGS_DIR,
    RAG_MIN_SCORE,
    RAG_TOP_K,
    ensure_directories,
)
from utils.embeddings_store import is_embedding_current, load_embedding, save_embedding
from utils.markdown import read_note


def _build_text(frontmatter: dict[str, Any], body: str) -> str:
    summary = str(frontmatter.get("summary", "") or "").strip()
    tags = " ".join(str(tag) for tag in frontmatter.get("tags", []) or [])
    content = body.strip()
    return " ".join(part for part in [summary, tags, content] if part)


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


def _load_note_payloads(project_root: Path) -> list[dict[str, Any]]:
    wiki_root = project_root / "wiki"
    note_paths = sorted(
        [path for path in wiki_root.rglob("*.md") if path.is_file() and "raw" not in path.parts]
    )
    payloads: list[dict[str, Any]] = []
    for note_path in note_paths:
        frontmatter, body = read_note(note_path)
        text = _build_text(frontmatter, body)
        payloads.append(
            {
                "path": note_path,
                "frontmatter": frontmatter,
                "body": body,
                "text": text,
            }
        )
    return payloads


def _llm_answer(question: str, context: str, source_ids: list[str]) -> str | None:
    try:
        from groq import Groq
    except Exception:
        return None

    from config import GROQ_API_KEY, LLM_MODEL

    if not GROQ_API_KEY or GROQ_API_KEY == "your_key_here":
        return None

    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Answer the user's question using only the provided context. "
                        "If the answer is not in the context, say so clearly. "
                        f"Cite sources as IDs: {', '.join(source_ids)}"
                    ),
                },
                {"role": "user", "content": f"Question: {question}\n\nContext:\n{context}"},
            ],
            response_format={"type": "json_object"},
        )
        payload = response.choices[0].message.content or "{}"
        parsed = json.loads(payload)
        answer = str(parsed.get("answer") or parsed.get("content") or "").strip()
        if answer:
            return answer
    except Exception:
        return None
    return None


def _fallback_answer(question: str, ranked_notes: list[tuple[float, dict[str, Any]]]) -> str:
    if not ranked_notes:
        return "I could not find enough relevant context in your notes to answer that question."

    top_score, top_note = ranked_notes[0]
    summary = str(top_note["frontmatter"].get("summary") or top_note["path"].stem).strip()
    body = top_note["body"].strip().splitlines()[0] if top_note["body"].strip() else ""
    if top_score < 0.3:
        return "I could not find enough relevant context in your notes to answer that question."
    if len(ranked_notes) == 1:
        if body:
            return f"Based on your note '{summary}', I can say: {body}"
        return f"Based on your note '{summary}', this appears to be the most relevant context."

    return (
        f"Based on {len(ranked_notes)} related notes, your notes suggest that {summary.lower()} is a strong match for your question."
    )


def ask(
    query: str,
    *,
    project_root: Path | None = None,
    top_k: int | None = None,
    min_score: float | None = None,
) -> dict[str, Any]:
    """Return an answer, source IDs, and confidence for a question over the local wiki notes."""
    project_root = project_root or Path(__file__).resolve().parent
    ensure_directories()

    top_k = top_k or RAG_TOP_K
    min_score = min_score if min_score is not None else RAG_MIN_SCORE
    payloads = _load_note_payloads(project_root)

    if not payloads:
        return {
            "answer": "No wiki notes are available yet. Capture and classify some notes first.",
            "sources": [],
            "confidence": "low",
        }

    model = _load_embedding_model()
    embeddings_dir = project_root / "data" / "embeddings"
    embeddings_dir.mkdir(parents=True, exist_ok=True)

    note_texts = []
    note_ids: list[str] = []
    for payload in payloads:
        note_id = str(payload["frontmatter"].get("id") or payload["path"].stem)
        note_ids.append(note_id)
        note_texts.append(payload["text"])

    all_texts = [query] + note_texts
    vectors = _embed_texts(model, all_texts)
    query_vector = vectors[0]

    ranked_notes: list[tuple[float, dict[str, Any]]] = []
    for idx, payload in enumerate(payloads, start=1):
        note_id = str(payload["frontmatter"].get("id") or payload["path"].stem)
        note_text = payload["text"]
        if not is_embedding_current(note_id, note_text, "sentence-transformers/all-MiniLM-L6-v2", embeddings_dir):
            save_embedding(note_id, vectors[idx], "sentence-transformers/all-MiniLM-L6-v2", note_text, embeddings_dir)

        score = _cosine_similarity(query_vector, vectors[idx])
        if score >= min_score:
            ranked_notes.append((score, payload))

    ranked_notes.sort(key=lambda item: item[0], reverse=True)
    top_matches = ranked_notes[:top_k]

    if not top_matches:
        return {
            "answer": "I could not find enough relevant context in your notes to answer that question.",
            "sources": [],
            "confidence": "low",
        }

    source_ids = [str(match[1]["frontmatter"].get("id") or match[1]["path"].stem) for match in top_matches]
    context_parts = []
    for score, payload in top_matches:
        note_id = str(payload["frontmatter"].get("id") or payload["path"].stem)
        summary = str(payload["frontmatter"].get("summary") or payload["path"].stem).strip()
        context_parts.append(f"[{note_id}] {summary}\n{payload['body'].strip()}")

    context_text = "\n\n".join(context_parts)
    answer = _llm_answer(query, context_text, source_ids)
    if not answer:
        answer = _fallback_answer(query, top_matches)

    best_score = top_matches[0][0]
    if best_score >= 0.75:
        confidence = "high"
    elif best_score >= min_score:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "answer": answer,
        "sources": source_ids,
        "confidence": confidence,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ask questions over your local wiki notes")
    parser.add_argument("question", nargs="+", help="Question to answer")
    args = parser.parse_args(argv)

    question = " ".join(args.question)
    result = ask(question)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
