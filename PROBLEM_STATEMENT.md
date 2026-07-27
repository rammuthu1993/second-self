# SecondSelf — Problem Statement

Every notes app fails the same way: you capture hundreds of notes, bookmarks, PDFs, and ideas — and then you never find them again. Information goes in, but nothing comes back out. Notes sit in folders nobody re-reads. Bookmarks pile up unread. Knowledge doesn't compound.

## Goal

Build an end-to-end system where you can capture **anything** (a note, a link, a file), have AI automatically classify and file it, auto-link it to related knowledge, render it as a live interactive graph you can explore, and — most importantly — **ask it any question in plain English and get an answer synthesized from your own accumulated knowledge**. Then deploy it to a public URL anyone can open.

**Not a notes app. Not a chatbot. A brain that organizes itself and answers for you.**

## Final System

```
Capture any note/link/file
        ↓
AI classifies & files it (PARA method)
        ↓
AI auto-links it to related notes (embeddings)
        ↓
Everything renders as a live, interactive, hoverable graph
        ↓
Ask it anything in plain English → answer pulled from YOUR notes
        ↓
Deployed on a public URL anyone can open
```

## Weekly Milestones

Each week is a self-contained problem. Build it, test it on **real** data (your own notes — not test data), and each week's output becomes the next week's input.

### Week 1 — The Archivist: "Capture Everything, Lose Nothing"

**Problem:** You have no single place to put things. Ideas, links, and notes scatter across apps, browser tabs, and your memory.

**Build:** One command that captures anything into `raw/` with timestamp + unique ID.

**Deliverable:** Working capture pipeline + 10+ real captured items.

**Badge:** 🏅 The Archivist

### Week 2 — The Librarian: "Teach AI to Organize For You"

**Problem:** A pile of raw captures is still a mess. Manual tagging never happens.

**Build:**
- Auto-classify with PARA (Projects, Areas, Resources, Archives), tags, and summary via Groq/Llama 3
- Auto-link related notes using embeddings (sentence-transformers)

**Deliverable:** Self-organizing `wiki/` with 15+ linked real notes.

**Badge:** 🏅 The Librarian

### Week 3 — The Cartographer: "Visualize the Brain"

**Problem:** Your knowledge is organized and linked — but you can't *see* it.

**Build:**
- Export notes and links to `graph.json` (nodes + edges)
- Render an interactive force-directed graph (vis-network) with hover, drag, and zoom

**Deliverable:** Living brain graph built from your real notes.

**Badge:** 🏅 The Cartographer

### Week 4 — The Oracle: "Ask It Anything, Ship It Public"

**Problem:** A visual brain is beautiful, but the real payoff is **answers**.

**Build:**
- `ask()` — retrieval-augmented Q&A over your wiki (embeddings + LLM)
- Streamlit app combining graph + search bar
- Deploy to Streamlit Cloud or Hugging Face Spaces

**Deliverable:** Full SecondSelf product with a public URL.

**Badge:** 🏅 The Oracle

## Final Deliverables

- [ ] Public GitHub repo with clean README + setup instructions
- [ ] Live deployed URL — interactive graph + ask-your-brain search
- [ ] End-to-end flow verified: capture → classify → link → graph → ask
- [ ] All 4 weekly milestones complete

## Related Documents

- [architecture.md](./architecture.md) — how the system is built
- [implementation-plan.md](./implementation-plan.md) — phase-wise build plan
- [edge-case.md](./edge-case.md) — corner scenarios and mitigations
