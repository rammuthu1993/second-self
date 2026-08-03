"""
Modern Dark & Light Blue UX Dashboard for RAG Wiki Assistant.
Run with: streamlit run dashboard.py
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import streamlit as st

# Configs & helper imports
from config import (
    EMBEDDINGS_DIR,
    RAG_MIN_SCORE,
    RAG_TOP_K,
    ensure_directories,
)
from utils.embeddings_store import is_embedding_current, save_embedding
from utils.markdown import read_note

# ==============================================================================
# 1. PAGE CONFIGURATION & DARK BLUE THEME STYLING
# ==============================================================================
st.set_page_config(
    page_title="AuraWiki AI - Intelligence Hub",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for Dark & Electric Light Blue Theme + Dark Quick Note Section
st.markdown(
    """
    <style>
    /* Dark Theme Backgrounds */
    .stApp {
        background-color: #0b132b;
        color: #e0e1dd;
    }
    
    /* Hero Header Banner */
    .hero-banner {
        background: linear-gradient(135deg, #1c2541 0%, #0b132b 100%);
        border: 1px solid #3a506b;
        border-left: 6px solid #60a5fa;
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    
    .hero-title {
        color: #60a5fa;
        font-size: 2.2rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.5px;
    }
    
    .hero-subtitle {
        color: #93c5fd;
        font-size: 1rem;
        margin-top: 0.4rem;
        opacity: 0.9;
    }
    
    /* Electric Metric Cards */
    .metric-card {
        background: #1c2541;
        border: 1px solid rgba(96, 165, 250, 0.2);
        padding: 1.2rem;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #60a5fa;
    }
    
    .metric-label {
        font-size: 0.85rem;
        color: #93c5fd;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* Response & Source Cards */
    .response-card {
        background: #1c2541;
        border: 1px solid #3a506b;
        border-radius: 10px;
        padding: 1.5rem;
        margin-top: 1rem;
        box-shadow: 0 4px 20px rgba(11, 19, 43, 0.5);
    }

    /* Confidence Badges */
    .badge-high {
        background-color: rgba(34, 197, 94, 0.2);
        color: #4ade80;
        border: 1px solid #22c55e;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    
    .badge-medium {
        background-color: rgba(234, 179, 8, 0.2);
        color: #facc15;
        border: 1px solid #eab308;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    
    .badge-low {
        background-color: rgba(239, 68, 68, 0.2);
        color: #f87171;
        border: 1px solid #ef4444;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.8rem;
    }

    /* ---- Dark Quick Note Styling ---- */
    .dark-note-card {
        background-color: #080d1a;
        border: 1px solid rgba(96, 165, 250, 0.25);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    }

    div[data-baseweb="textarea"] {
        background-color: #0b132b !important;
        border: 1px solid #3a506b !important;
        border-radius: 8px !important;
    }

    div[data-baseweb="textarea"] textarea {
        color: #e0e1dd !important;
        font-family: 'Inter', monospace;
        font-size: 0.98rem;
        caret-color: #60a5fa;
    }

    div[data-baseweb="textarea"]:focus-within {
        border-color: #60a5fa !important;
        box-shadow: 0 0 0 1px #60a5fa !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# 2. BACKEND RAG FUNCTIONS
# ==============================================================================
def _build_text(frontmatter: dict[str, Any], body: str) -> str:
    summary = str(frontmatter.get("summary", "") or "").strip()
    tags = " ".join(str(tag) for tag in frontmatter.get("tags", []) or [])
    content = body.strip()
    return " ".join(part for part in [summary, tags, content] if part)


@st.cache_resource(show_spinner=False)
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
    if not wiki_root.exists():
        return []

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

    return f"Based on {len(ranked_notes)} related notes, your notes suggest that {summary.lower()} is a strong match for your question."


def ask_engine(
    query: str,
    project_root: Path,
    top_k: int,
    min_score: float,
) -> dict[str, Any]:
    ensure_directories()
    payloads = _load_note_payloads(project_root)

    if not payloads:
        return {
            "answer": "No wiki notes were found in your `/wiki` directory. Please add some markdown notes.",
            "sources": [],
            "matches": [],
            "confidence": "low",
        }

    model = _load_embedding_model()
    embeddings_dir = project_root / "data" / "embeddings"
    embeddings_dir.mkdir(parents=True, exist_ok=True)

    note_texts, note_ids = [], []
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
        if not is_embedding_current(
            note_id, note_text, "sentence-transformers/all-MiniLM-L6-v2", embeddings_dir
        ):
            save_embedding(
                note_id,
                vectors[idx],
                "sentence-transformers/all-MiniLM-L6-v2",
                note_text,
                embeddings_dir,
            )

        score = _cosine_similarity(query_vector, vectors[idx])
        if score >= min_score:
            ranked_notes.append((score, payload))

    ranked_notes.sort(key=lambda item: item[0], reverse=True)
    top_matches = ranked_notes[:top_k]

    if not top_matches:
        return {
            "answer": "I could not find enough relevant context in your notes to answer that question.",
            "sources": [],
            "matches": [],
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
    confidence = "high" if best_score >= 0.75 else ("medium" if best_score >= min_score else "low")

    return {
        "answer": answer,
        "sources": source_ids,
        "matches": top_matches,
        "confidence": confidence,
    }


def save_single_field_dark_note(raw_text: str, project_root: Path) -> Path:
    """Saves a note from a single input field into /wiki as formatted Markdown."""
    wiki_dir = project_root / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)

    lines = [line.strip() for line in raw_text.strip().splitlines() if line.strip()]
    first_line = lines[0] if lines else "Quick Note"

    title = first_line[:50].rstrip(":#- ")
    safe_filename = re.sub(r"[^\w\-_]", "_", title.lower().strip()) or "note"
    file_path = wiki_dir / f"{safe_filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    summary = first_line if len(first_line) <= 120 else first_line[:117] + "..."

    markdown_content = f"""---
id: {safe_filename}
summary: "{summary}"
tags: ["quick-note"]
created: "{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
---

# {title}

{raw_text.strip()}
"""
    file_path.write_text(markdown_content, encoding="utf-8")
    return file_path


# ==============================================================================
# 3. DASHBOARD USER INTERFACE
# ==============================================================================
def main() -> None:
    project_root = Path(__file__).resolve().parent
    payloads = _load_note_payloads(project_root)

    # --- Electric Light Blue Header Banner ---
    st.markdown(
        """
        <div class="hero-banner">
            <h1 class="hero-title">⚡ AuraWiki Intelligence Hub</h1>
            <p class="hero-subtitle">Retrieval-Augmented Question Answering Engine for Local Knowledge</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Sidebar Parameters & Controls ---
    with st.sidebar:
        st.markdown("### 🎛️ Engine Configuration")
        st.markdown("---")
        
        top_k = st.slider(
            "Top Context Matches (Top K)",
            min_value=1,
            max_value=10,
            value=RAG_TOP_K,
            help="Maximum number of relevant notes to pull for LLM analysis.",
        )

        min_score = st.slider(
            "Similarity Cutoff (Min Score)",
            min_value=0.0,
            max_value=1.0,
            value=float(RAG_MIN_SCORE),
            step=0.05,
            help="Filters out notes below this vector cosine similarity threshold.",
        )

        st.markdown("---")
        st.markdown("### 📊 Knowledge Metrics")
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-value">{len(payloads)}</div>
                    <div class="metric-label">Notes</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col_s2:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-value">{top_k}</div>
                    <div class="metric-label">Top K</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # --- Main Interface Tabs ---
    tab_query, tab_wiki, tab_quick_note = st.tabs(
        ["🔍 Ask Engine", "📂 Explore Wiki Workspace", "📝 Quick Note"]
    )

    # --- TAB 1: ASK ENGINE ---
    with tab_query:
        query_input = st.text_input(
            "Ask any question regarding your local notes:",
            placeholder="e.g. What were the takeaways from the latest architecture meeting?",
            key="rag_query_input",
        )

        col_btn, col_blank = st.columns([1, 4])
        with col_btn:
            submit = st.button("Generate Answer", type="primary", use_container_width=True)

        if submit or query_input:
            if not query_input.strip():
                st.warning("Please enter a valid query.")
            else:
                with st.spinner("Analyzing embeddings & building response..."):
                    result = ask_engine(
                        query_input,
                        project_root=project_root,
                        top_k=top_k,
                        min_score=min_score,
                    )

                # Response UI Layout
                st.markdown("---")
                
                # Confidence Badge Logic
                conf = result["confidence"]
                badge_class = f"badge-{conf}"
                
                st.markdown(
                    f"""
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <h3 style="color: #60a5fa; margin: 0;">AI Generated Answer</h3>
                        <span class="{badge_class}">CONFIDENCE: {conf.upper()}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Main Answer Display Box
                st.markdown(
                    f"""
                    <div class="response-card">
                        <p style="font-size: 1.1rem; line-height: 1.6; color: #e0e1dd; margin: 0;">
                            {result['answer']}
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Source Accordion Display
                if result["matches"]:
                    st.markdown("### 📑 Context Sources Used")
                    for score, note_payload in result["matches"]:
                        note_id = str(note_payload["frontmatter"].get("id") or note_payload["path"].stem)
                        summary = str(note_payload["frontmatter"].get("summary") or note_payload["path"].stem).strip()

                        with st.expander(f"🔹 **[{note_id}]** {summary} — *Score: {score:.3f}*"):
                            st.markdown(f"**Path:** `{note_payload['path']}`")
                            st.markdown("**Excerpt:**")
                            st.code(note_payload["body"][:350] + ("..." if len(note_payload["body"]) > 350 else ""))

    # --- TAB 2: EXPLORE WIKI ---
    with tab_wiki:
        st.subheader("Wiki Knowledge Explorer")
        if not payloads:
            st.info("No markdown notes found in `/wiki` directory.")
        else:
            selected_note = st.selectbox(
                "Select a note to inspect:",
                options=payloads,
                format_func=lambda p: f"{p['frontmatter'].get('id', p['path'].stem)} | {p['frontmatter'].get('summary', p['path'].name)}",
            )

            if selected_note:
                col_meta, col_body = st.columns([1, 2])
                with col_meta:
                    st.markdown("#### Frontmatter Metadata")
                    st.json(selected_note["frontmatter"])
                with col_body:
                    st.markdown("#### Note Body")
                    st.markdown(selected_note["body"])

    # --- TAB 3: DARK QUICK NOTE ---
    with tab_quick_note:
        st.markdown(
            """
            <div class="dark-note-card">
                <h3 style="color: #60a5fa; margin-top: 0;">📝 Quick Note</h3>
                <p style="color: #93c5fd; font-size: 0.9rem; margin-bottom: 0;">
                    Type a quick thought in the field below. It will automatically save directly into your <code>/wiki</code> directory.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("dark_quick_note_form", clear_on_submit=True):
            raw_note = st.text_area(
                "",
                height=200,
                placeholder="Type your note or idea here...",
                label_visibility="collapsed",
            )

            submit_btn = st.form_submit_button("💾 Save Quick Note", use_container_width=True)

            if submit_btn:
                if not raw_note.strip():
                    st.error("Note content cannot be empty.")
                else:
                    saved_path = save_single_field_dark_note(raw_note, project_root)
                    st.success(f"Saved note to `/wiki/{saved_path.name}`")


if __name__ == "__main__":
    main()