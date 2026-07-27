# SecondSelf — Edge Cases & Corner Scenarios

This document catalogs edge cases, failure modes, and corner scenarios for the SecondSelf project. It is derived from [architecture.md](./architecture.md) and [implementation-plan.md](./implementation-plan.md).

**How to use this doc:**

- Implement defensive handling during each phase (not only at the end).
- Add new edge cases discovered during testing under [§12 Discovered During Testing](#12-discovered-during-testing).
- Each entry includes: **Scenario → Impact → Expected behavior → Mitigation**.

---

## Severity Legend

| Level | Meaning |
|-------|---------|
| 🔴 **Critical** | Data loss, security risk, or pipeline crash |
| 🟠 **High** | Wrong output (bad classification, hallucinated answer) |
| 🟡 **Medium** | Degraded UX or partial failure |
| 🟢 **Low** | Cosmetic or rare; graceful fallback acceptable |

---

## 1. Capture Pipeline (`capture.py`) — Phase 1

### EC-CAP-01 — Empty note text

| Field | Detail |
|-------|--------|
| **Scenario** | User runs `python capture.py note ""` or only whitespace |
| **Impact** | 🟡 Empty raw file pollutes wiki and embeddings |
| **Expected** | Reject with clear error: "Note content cannot be empty" |
| **Mitigation** | Validate `strip()` length > 0 before writing |

### EC-CAP-02 — Very long note (10k+ chars)

| Field | Detail |
|-------|--------|
| **Scenario** | User pastes an entire article or log dump |
| **Impact** | 🟡 LLM classify may truncate; embedding quality drops |
| **Expected** | Capture succeeds (raw is append-only); optionally warn if > N chars |
| **Mitigation** | Store full content in raw/; truncate only when sending to LLM in classify |

### EC-CAP-03 — Special characters & Unicode in note body

| Field | Detail |
|-------|--------|
| **Scenario** | Emoji, Hindi/Chinese text, code blocks with `{`, `}`, `---` |
| **Impact** | 🔴 YAML frontmatter parse failure if unescaped |
| **Expected** | Capture saves correctly; frontmatter uses safe YAML quoting |
| **Mitigation** | Use `pyyaml` safe_dump with `allow_unicode=True`; never hand-build YAML strings |

### EC-CAP-04 — Multiline note from CLI (Windows PowerShell)

| Field | Detail |
|-------|--------|
| **Scenario** | User tries to pass multiline string on Windows |
| **Impact** | 🟡 Only first line captured or quoting breaks |
| **Expected** | Document workaround: heredoc, file input, or `capture.py note --file note.txt` |
| **Mitigation** | Support `--file` flag for multiline notes (recommended enhancement) |

### EC-CAP-05 — Invalid or malformed URL

| Field | Detail |
|-------|--------|
| **Scenario** | `python capture.py link "not-a-url"` or `ftp://internal` |
| **Impact** | 🟡 Broken link capture; fetch errors |
| **Expected** | Validate URL scheme (`http`, `https` only); reject others with error |
| **Mitigation** | `urllib.parse` validation before fetch |

### EC-CAP-06 — Link fetch timeout / unreachable host

| Field | Detail |
|-------|--------|
| **Scenario** | Site is down, DNS fails, or slow response |
| **Impact** | 🟡 Capture hangs or fails entirely |
| **Expected** | Capture still saves URL + error message in body; `status: unprocessed` |
| **Mitigation** | `requests.get(timeout=10)`; catch exceptions; never block capture on fetch failure |

### EC-CAP-07 — Link to login-walled or JS-rendered page

| Field | Detail |
|-------|--------|
| **Scenario** | Twitter/X, LinkedIn, SPA sites return empty HTML |
| **Impact** | 🟡 Raw body is useless for classify/link |
| **Expected** | Store URL + fetched title (if any) + note "content unavailable" |
| **Mitigation** | Classify from URL + domain + any snippet; don't assume fetch success |

### EC-CAP-08 — Large file upload (>50 MB PDF)

| Field | Detail |
|-------|--------|
| **Scenario** | User captures a huge PDF or video renamed as PDF |
| **Impact** | 🔴 Disk fill, slow embedding, deploy bloat |
| **Expected** | Reject or warn above `MAX_FILE_SIZE` (e.g. 10 MB) |
| **Mitigation** | Configurable size limit in `config.py`; check before copy |

### EC-CAP-09 — Unsupported file type (.docx, .zip, .exe)

| Field | Detail |
|-------|--------|
| **Scenario** | User captures non-PDF/non-txt file |
| **Impact** | 🟡 No text extracted; empty wiki body |
| **Expected** | Copy file to `assets/files/`; store metadata; body = "[Binary file — no text extracted]" |
| **Mitigation** | Whitelist extensions: `.pdf`, `.txt`, `.md`; warn on others |

### EC-CAP-10 — PDF with no extractable text (scanned image)

| Field | Detail |
|-------|--------|
| **Scenario** | Scanned PDF — `pypdf` returns empty string |
| **Impact** | 🟠 Classify/link have nothing to work with |
| **Expected** | Capture succeeds; body notes "No text extracted (possibly scanned PDF)" |
| **Mitigation** | OCR out of scope for MVP; document limitation in README |

### EC-CAP-11 — File path does not exist

| Field | Detail |
|-------|--------|
| **Scenario** | `python capture.py file "./missing.pdf"` |
| **Impact** | 🟢 User error |
| **Expected** | Clear error: "File not found: {path}"; exit code 1 |
| **Mitigation** | `Path.exists()` check before processing |

### EC-CAP-12 — Duplicate capture of same content

| Field | Detail |
|-------|--------|
| **Scenario** | User captures the same link or note twice |
| **Impact** | 🟡 Duplicate nodes in graph; redundant links |
| **Expected** | Each capture gets unique ID (by design — append-only raw/) |
| **Mitigation** | Optional dedup in classify by URL hash or content hash (post-MVP) |

### EC-CAP-13 — Concurrent captures (two terminals at once)

| Field | Detail |
|-------|--------|
| **Scenario** | Two `capture.py` runs write simultaneously |
| **Impact** | 🟢 Low — UUID filenames prevent collision |
| **Expected** | Both succeed with different IDs |
| **Mitigation** | UUID in filename; no shared mutable state during capture |

### EC-CAP-14 — `raw/` directory missing

| Field | Detail |
|-------|--------|
| **Scenario** | User deletes `raw/` or runs before Phase 0 setup |
| **Impact** | 🔴 Write failure |
| **Expected** | Auto-create `raw/` (and parent dirs) on first capture |
| **Mitigation** | `Path.mkdir(parents=True, exist_ok=True)` in capture init |

---

## 2. Auto-Classify (`classify.py`) — Phase 2

### EC-CLS-01 — Missing or invalid `GROQ_API_KEY`

| Field | Detail |
|-------|--------|
| **Scenario** | `.env` missing, key empty, or revoked |
| **Impact** | 🔴 Classify fails for all items |
| **Expected** | Fail fast with: "GROQ_API_KEY not set. See .env.example" |
| **Mitigation** | Check key in `config.py` at startup; never log key value |

### EC-CLS-02 — Groq API rate limit (429)

| Field | Detail |
|-------|--------|
| **Scenario** | Batch classify of 20+ notes hits free tier limit |
| **Impact** | 🟠 Partial wiki — some notes unprocessed |
| **Expected** | Retry with exponential backoff; leave raw as `unprocessed` on failure |
| **Mitigation** | `time.sleep()` between calls; `--id` for single retry; log failed IDs |

### EC-CLS-03 — Groq API timeout or 5xx

| Field | Detail |
|-------|--------|
| **Scenario** | Network blip or Groq outage |
| **Impact** | 🟠 Stuck unprocessed raw files |
| **Expected** | Retry up to 3 times; don't mark raw as processed on failure |
| **Mitigation** | Idempotent classify — safe to re-run |

### EC-CLS-04 — LLM returns malformed JSON

| Field | Detail |
|-------|--------|
| **Scenario** | Model wraps JSON in markdown fences or adds prose |
| **Impact** | 🟠 Classify crashes for that item |
| **Expected** | Strip fences; parse retry; fallback to `Resources` + raw title |
| **Mitigation** | Robust JSON extractor; validate schema before wiki write |

### EC-CLS-05 — LLM returns invalid PARA category

| Field | Detail |
|-------|--------|
| **Scenario** | Model returns `"Project"` or `"Misc"` instead of exact PARA name |
| **Impact** | 🟠 File written to wrong/missing folder |
| **Expected** | Map fuzzy matches; default to `Resources` if unmapped |
| **Mitigation** | Allowlist: `Projects`, `Areas`, `Resources`, `Archives` only |

### EC-CLS-06 — LLM hallucinates tags unrelated to content

| Field | Detail |
|-------|--------|
| **Scenario** | Generic tags like `general`, `note`, `misc` on every item |
| **Impact** | 🟡 Noisy graph labels; weak retrieval |
| **Expected** | Accept but tune prompt: "tags must appear in or relate to content" |
| **Mitigation** | Prompt engineering; post-filter banned generic tags |

### EC-CLS-07 — Summary exceeds 120 chars

| Field | Detail |
|-------|--------|
| **Scenario** | LLM ignores length constraint |
| **Impact** | 🟢 Long graph node labels |
| **Expected** | Truncate summary to 120 chars with `...` for display |
| **Mitigation** | Hard truncate after LLM response |

### EC-CLS-08 — Slug collision in wiki path

| Field | Detail |
|-------|--------|
| **Scenario** | Two notes classify to same slug (e.g. `meeting-notes.md`) |
| **Impact** | 🔴 Second note overwrites first |
| **Expected** | Append short ID to slug: `meeting-notes-a1b2c3d4.md` |
| **Mitigation** | `slug + id[:8]` uniqueness check before write |

### EC-CLS-09 — Raw file already `processed` but wiki missing

| Field | Detail |
|-------|--------|
| **Scenario** | User deletes wiki file manually; raw still says processed |
| **Impact** | 🟠 Orphan raw — never re-classified |
| **Expected** | Support `--force` flag to re-process; or detect missing wiki by `raw_id` |
| **Mitigation** | `classify.py --force --id {uuid}` |

### EC-CLS-10 — Raw frontmatter corrupted

| Field | Detail |
|-------|--------|
| **Scenario** | Manual edit breaks YAML in raw file |
| **Impact** | 🟠 Skip or crash on that file |
| **Expected** | Log warning; skip file; continue batch |
| **Mitigation** | Try/except around frontmatter parse per file |

### EC-CLS-11 — Empty raw body (link fetch failed + no content)

| Field | Detail |
|-------|--------|
| **Scenario** | Link capture with no fetched text |
| **Impact** | 🟡 LLM classifies from URL only — may be vague |
| **Expected** | Classify using URL + any metadata; tag as `bookmark` |
| **Mitigation** | Include `url` field in LLM prompt context |

### EC-CLS-12 — `data/index.json` corrupt or missing

| Field | Detail |
|-------|--------|
| **Scenario** | Invalid JSON or first run |
| **Impact** | 🟡 Index out of sync with wiki |
| **Expected** | Rebuild index from wiki/ on load failure |
| **Mitigation** | `rebuild_index()` utility function |

---

## 3. Auto-Link (`link.py`) — Phase 3

### EC-LNK-01 — Only one wiki note exists

| Field | Detail |
|-------|--------|
| **Scenario** | User runs link.py with 1 note |
| **Impact** | 🟢 No links possible |
| **Expected** | Complete successfully; no links added; no error |
| **Mitigation** | Early return if note count < 2 |

### EC-LNK-02 — Similarity threshold too low (0.50)

| Field | Detail |
|-------|--------|
| **Scenario** | Unrelated notes linked (e.g. all "work" notes) |
| **Impact** | 🟠 Graph becomes hairball; bad RAG context |
| **Expected** | Document tuning; default 0.72 |
| **Mitigation** | Raise threshold; cap max links per note (e.g. 5) |

### EC-LNK-03 — Similarity threshold too high (0.90)

| Field | Detail |
|-------|--------|
| **Scenario** | Clearly related notes not linked |
| **Impact** | 🟡 Sparse graph |
| **Expected** | User lowers threshold via `--threshold` |
| **Mitigation** | Document tuning in README |

### EC-LNK-04 — Re-running link.py creates duplicate links

| Field | Detail |
|-------|--------|
| **Scenario** | User runs link twice |
| **Impact** | 🟡 Duplicate `[[links]]` in body and frontmatter |
| **Expected** | Idempotent — check existing links before insert |
| **Mitigation** | Set-based link IDs in frontmatter; dedupe wiki links in body |

### EC-LNK-05 — Embedding model first download fails (offline)

| Field | Detail |
|-------|--------|
| **Scenario** | No internet on first `sentence-transformers` run |
| **Impact** | 🔴 link.py crashes |
| **Expected** | Clear error: "Model download failed. Check network." |
| **Mitigation** | Pre-download model during Phase 0 setup |

### EC-LNK-06 — Note edited after embedding cached

| Field | Detail |
|-------|--------|
| **Scenario** | User edits wiki body; embedding stale |
| **Impact** | 🟠 Wrong similarity scores |
| **Expected** | Re-embed when `text_hash` changes |
| **Mitigation** | Compare content hash in `embeddings_store.py` |

### EC-LNK-07 — Very short notes ("ok", "todo")

| Field | Detail |
|-------|--------|
| **Scenario** | Tiny notes embed similarly to everything |
| **Impact** | 🟠 False positive links |
| **Expected** | Skip linking for notes below min length (e.g. 20 chars) |
| **Mitigation** | Min content length gate before embedding |

### EC-LNK-08 — O(n²) pairwise comparison slow at scale

| Field | Detail |
|-------|--------|
| **Scenario** | 500+ notes — link.py takes minutes |
| **Impact** | 🟡 Slow pipeline |
| **Expected** | Acceptable for MVP (<100 notes); document scale limit |
| **Mitigation** | Post-MVP: FAISS index, batch numpy matrix |

### EC-LNK-09 — Broken wiki link target (link to deleted note ID)

| Field | Detail |
|-------|--------|
| **Scenario** | Note deleted but other notes still reference its ID |
| **Impact** | 🟡 Dangling edges in graph |
| **Expected** | build_graph skips edges to missing nodes; log warning |
| **Mitigation** | Orphan link cleanup script (optional) |

### EC-LNK-10 — Notes in different languages

| Field | Detail |
|-------|--------|
| **Scenario** | Mix of English and Hindi notes |
| **Impact** | 🟡 MiniLM cross-lingual similarity weaker |
| **Expected** | Links may miss cross-language relations |
| **Mitigation** | Document limitation; consider multilingual model post-MVP |

---

## 4. Graph Build & UI (`build_graph.py`, vis-network) — Phase 4

### EC-GRF-01 — Empty wiki (no classified notes)

| Field | Detail |
|-------|--------|
| **Scenario** | User runs build_graph before classify |
| **Impact** | 🟡 Empty graph.json |
| **Expected** | Export valid JSON with `node_count: 0`; UI shows "No notes yet" |
| **Mitigation** | Empty state in Streamlit component |

### EC-GRF-02 — Wiki note missing required frontmatter fields

| Field | Detail |
|-------|--------|
| **Scenario** | Manual wiki edit removes `id` or `category` |
| **Impact** | 🟠 Node skipped or malformed |
| **Expected** | Skip invalid notes; log path; continue build |
| **Mitigation** | Validate required fields; use filename as fallback ID |

### EC-GRF-03 — Duplicate node IDs in graph

| Field | Detail |
|-------|--------|
| **Scenario** | Two wiki files share same `id` (manual error) |
| **Impact** | 🔴 vis-network breaks or merges nodes |
| **Expected** | Last-write-wins or dedupe with warning |
| **Mitigation** | Assert unique IDs during build; fail with clear message |

### EC-GRF-04 — Edge points to non-existent node

| Field | Detail |
|-------|--------|
| **Scenario** | Stale link ID in frontmatter |
| **Impact** | 🟡 vis-network warning or missing edge |
| **Expected** | Filter orphan edges; include in build log |
| **Mitigation** | Validate source/target exist before adding edge |

### EC-GRF-05 — graph.json stale after new classify/link

| Field | Detail |
|-------|--------|
| **Scenario** | User adds notes but doesn't rebuild graph |
| **Impact** | 🟡 UI shows old brain |
| **Expected** | Document: run `build_graph.py` after pipeline; optional auto-rebuild in app |
| **Mitigation** | "Refresh graph" button in Streamlit sidebar |

### EC-GRF-06 — Very large graph (200+ nodes)

| Field | Detail |
|-------|--------|
| **Scenario** | Browser slows; physics simulation laggy |
| **Impact** | 🟡 Poor UX |
| **Expected** | Graph still renders; may need physics tuning |
| **Mitigation** | Limit physics iterations; cluster by PARA category; filter toggle |

### EC-GRF-07 — Long preview text breaks tooltip

| Field | Detail |
|-------|--------|
| **Scenario** | Preview field is 10k chars |
| **Impact** | 🟢 UI overflow |
| **Expected** | Truncate preview to 200 chars in build_graph |
| **Mitigation** | Hard cap in node builder |

### EC-GRF-08 — Special chars in node label break JSON/HTML injection

| Field | Detail |
|-------|--------|
| **Scenario** | Summary contains `"`, `<script>`, newlines |
| **Impact** | 🔴 XSS in graph tooltip if unsanitized |
| **Expected** | JSON-encode properly; escape HTML in tooltip |
| **Mitigation** | Use `json.dumps` for injection; never string-concat raw content into JS |

### EC-GRF-09 — graph.json invalid JSON

| Field | Detail |
|-------|--------|
| **Scenario** | Partial write during crash |
| **Impact** | 🔴 App graph section crashes |
| **Expected** | Write to temp file then atomic rename |
| **Mitigation** | `graph.json.tmp` → `graph.json` pattern |

### EC-GRF-10 — vis-network fails inside Streamlit iframe

| Field | Detail |
|-------|--------|
| **Scenario** | CDN blocked, CSP issues, or component height 0 |
| **Impact** | 🟠 Blank graph panel |
| **Expected** | Fallback message; bundle vis-network locally if CDN fails |
| **Mitigation** | Set explicit component height (600px+); test in deployed env |

---

## 5. RAG Q&A (`ask.py`) — Phase 5

### EC-ASK-01 — Question with no relevant notes (low similarity)

| Field | Detail |
|-------|--------|
| **Scenario** | User asks "What's the weather?" — not in notes |
| **Impact** | 🟠 LLM hallucinates answer from thin context |
| **Expected** | Return: "I don't have enough in your notes to answer." |
| **Mitigation** | Enforce `RAG_MIN_SCORE` (0.45); check best score before LLM call |

### EC-ASK-02 — Question matches wrong notes (similar wording)

| Field | Detail |
|-------|--------|
| **Scenario** | "Python project" retrieves unrelated "Python snake" note |
| **Impact** | 🟠 Wrong answer |
| **Expected** | Return sources; user can verify; tune retrieval |
| **Mitigation** | Show source list with scores; increase top_k cautiously |

### EC-ASK-03 — Empty question submitted

| Field | Detail |
|-------|--------|
| **Scenario** | User clicks Ask with blank search bar |
| **Impact** | 🟢 Wasted API call |
| **Expected** | UI validation: disable Ask on empty input |
| **Mitigation** | Strip and check length in both UI and `ask()` |

### EC-ASK-04 — LLM hallucinates beyond retrieved context

| Field | Detail |
|-------|--------|
| **Scenario** | Model adds facts not in notes |
| **Impact** | 🔴 Core product trust failure |
| **Expected** | System prompt: "Answer ONLY from context. Say 'not in notes' if unsure." |
| **Mitigation** | Strict prompt; lower temperature; cite note IDs in answer |

### EC-ASK-05 — Retrieved context exceeds LLM token limit

| Field | Detail |
|-------|--------|
| **Scenario** | top_k=5 but each note is 5000 chars |
| **Impact** | 🟠 API error or truncated context |
| **Expected** | Truncate each note chunk to max chars (e.g. 1500 total context) |
| **Mitigation** | Smart chunking: summary + first N chars of body |

### EC-ASK-06 — Groq fails during ask()

| Field | Detail |
|-------|--------|
| **Scenario** | API down mid-query |
| **Impact** | 🟡 User sees error |
| **Expected** | Return error dict with retrieved sources still visible |
| **Mitigation** | Separate retrieval from synthesis; graceful error message |

### EC-ASK-07 — Question in language different from notes

| Field | Detail |
|-------|--------|
| **Scenario** | Hindi question, English notes |
| **Impact** | 🟡 Poor retrieval scores |
| **Expected** | Low confidence response; suggest rephrasing |
| **Mitigation** | Document limitation; multilingual embedding model post-MVP |

### EC-ASK-08 — Ambiguous question spanning many topics

| Field | Detail |
|-------|--------|
| **Scenario** | "Tell me everything I know" |
| **Impact** | 🟡 Over-broad retrieval |
| **Expected** | Synthesize from top_k; note partial coverage |
| **Mitigation** | Cap context; confidence = "low" when scores are spread |

### EC-ASK-09 — Stale embeddings vs updated wiki

| Field | Detail |
|-------|--------|
| **Scenario** | Wiki edited; ask() uses old cached vectors |
| **Impact** | 🟠 Retrieves outdated content |
| **Expected** | Re-run link.py after edits; or hash-check in ask retrieval |
| **Mitigation** | Reuse embeddings_store hash logic |

### EC-ASK-10 — No wiki notes exist yet

| Field | Detail |
|-------|--------|
| **Scenario** | ask() called before classify |
| **Impact** | 🟢 Empty retrieval |
| **Expected** | "No notes indexed yet. Run classify first." |
| **Mitigation** | Check wiki count at start of ask() |

---

## 6. Streamlit App (`app.py`) — Phase 5

### EC-APP-01 — App starts without graph.json

| Field | Detail |
|-------|--------|
| **Scenario** | Fresh clone; graph not built |
| **Impact** | 🟡 Graph section empty/errors |
| **Expected** | Friendly empty state + instructions to run build_graph.py |
| **Mitigation** | Check file exists on load |

### EC-APP-02 — File upload in sidebar exceeds Streamlit limit

| Field | Detail |
|-------|--------|
| **Scenario** | Default 200 MB upload config vs our 10 MB limit |
| **Impact** | 🟡 Confusing error |
| **Expected** | Validate size client-side message before save |
| **Mitigation** | Match `MAX_FILE_SIZE` in upload handler |

### EC-APP-03 — Streamlit session rerun loses in-progress question

| Field | Detail |
|-------|--------|
| **Scenario** | User types question; unrelated widget triggers rerun |
| **Impact** | 🟢 UX annoyance |
| **Expected** | Use `st.session_state` for question and answer |
| **Mitigation** | Persist query/result in session state |

### EC-APP-04 — Running full pipeline from UI blocks app

| Field | Detail |
|-------|--------|
| **Scenario** | Sidebar "Process all" runs classify+link+embed on 50 notes |
| **Impact** | 🟡 Streamlit timeout (app appears frozen) |
| **Expected** | Show spinner; run subprocess or background thread; warn on large batches |
| **Mitigation** | Recommend CLI for bulk; UI for single capture only |

### EC-APP-05 — Multiple users on public deployed app (no auth)

| Field | Detail |
|-------|--------|
| **Scenario** | Stranger opens public URL and submits questions |
| **Impact** | 🟡 Groq API usage; no data write if read-only deploy |
| **Expected** | MVP: read-only deployed app (pre-built wiki); no public capture |
| **Mitigation** | Disable capture on deploy; secrets only for ask() |

---

## 7. Deployment — Phases 8–9

### EC-DEP-01 — API key committed to GitHub

| Field | Detail |
|-------|--------|
| **Scenario** | `.env` accidentally pushed |
| **Impact** | 🔴 Key theft, billing abuse |
| **Expected** | `.gitignore` blocks `.env`; use platform secrets |
| **Mitigation** | Pre-push checklist; rotate key if leaked |

### EC-DEP-02 — Personal/sensitive notes in public repo

| Field | Detail |
|-------|--------|
| **Scenario** | Real journal entries pushed for demo |
| **Impact** | 🔴 Privacy breach |
| **Expected** | Ship anonymized sample wiki; gitignore `raw/` |
| **Mitigation** | Review repo before push; use demo dataset |

### EC-DEP-03 — Streamlit Cloud build timeout (sentence-transformers)

| Field | Detail |
|-------|--------|
| **Scenario** | Heavy deps exceed build limit |
| **Impact** | 🔴 Deploy fails |
| **Expected** | Pre-build embeddings locally; lazy-load model or use HF Spaces |
| **Mitigation** | MVP: bundle pre-computed embeddings + graph; ask() only needs Groq |

### EC-DEP-04 — Ephemeral filesystem on Streamlit Cloud

| Field | Detail |
|-------|--------|
| **Scenario** | Capture via UI writes files that disappear on restart |
| **Impact** | 🟠 Data loss in production |
| **Expected** | Document: deployed app is demo/read-only |
| **Mitigation** | Disable write pipeline on cloud; local-first capture |

### EC-DEP-05 — graph.json too large for git / slow page load

| Field | Detail |
|-------|--------|
| **Scenario** | 1000+ node graph |
| **Impact** | 🟡 Slow initial load |
| **Expected** | Compress JSON; paginate or filter in UI |
| **Mitigation** | Cap demo dataset size for public deploy |

### EC-DEP-06 — Missing secret on deploy platform

| Field | Detail |
|-------|--------|
| **Scenario** | `GROQ_API_KEY` not set in Streamlit secrets |
| **Impact** | 🟠 ask() fails on live site |
| **Expected** | Graceful error in UI; graph still works |
| **Mitigation** | Feature-detect key; show setup instructions in sidebar |

### EC-DEP-07 — Windows paths break on Linux deploy

| Field | Detail |
|-------|--------|
| **Scenario** | Hardcoded `\` in paths |
| **Impact** | 🔴 File not found on cloud |
| **Expected** | Always use `pathlib.Path` |
| **Mitigation** | Phase 6 test on path resolution |

---

## 8. Data Integrity & File System

### EC-FS-01 — Manual edit desyncs raw vs wiki vs index

| Field | Detail |
|-------|--------|
| **Scenario** | User edits files by hand inconsistently |
| **Impact** | 🟠 Pipeline state unknown |
| **Expected** | Document: prefer CLI; provide rebuild utilities |
| **Mitigation** | `rebuild_index()`, `build_graph.py` as source of truth for derived data |

### EC-FS-02 — Disk full during write

| Field | Detail |
|-------|--------|
| **Scenario** | No space left on device |
| **Impact** | 🔴 Partial/corrupt files |
| **Expected** | Atomic writes; clear OS error propagated |
| **Mitigation** | Write temp then rename |

### EC-FS-03 — Filename encoding issues (non-ASCII filenames)

| Field | Detail |
|-------|--------|
| **Scenario** | PDF named `报告.pdf` on Windows |
| **Impact** | 🟡 Copy or path errors |
| **Expected** | Sanitize stored filename to ASCII slug + preserve original in frontmatter |
| **Mitigation** | `slugify(original_filename)` for assets path |

### EC-FS-04 — Clock skew / timezone confusion in timestamps

| Field | Detail |
|-------|--------|
| **Scenario** | Captures sort wrong across timezones |
| **Impact** | 🟢 Cosmetic ordering |
| **Expected** | Always store ISO8601 with timezone offset |
| **Mitigation** | `datetime.now(timezone.utc).isoformat()` or local with offset |

---

## 9. Security

### EC-SEC-01 — SSRF via link capture

| Field | Detail |
|-------|--------|
| **Scenario** | User captures `http://169.254.169.254/` or internal IP |
| **Impact** | 🔴 Internal network probe |
| **Expected** | Block private IP ranges; http/https only |
| **Mitigation** | URL allowlist; no redirect following to internal hosts |

### EC-SEC-02 — Malicious PDF (zip bomb / exploit)

| Field | Detail |
|-------|--------|
| **Scenario** | Crafted PDF crashes parser |
| **Impact** | 🟠 DoS on capture |
| **Expected** | Catch parser exceptions; skip text extraction |
| **Mitigation** | Size limits; try/except around pypdf |

### EC-SEC-03 — Prompt injection in note content

| Field | Detail |
|-------|--------|
| **Scenario** | Note contains "Ignore previous instructions..." |
| **Impact** | 🟠 Wrong PARA category or leaked prompt behavior |
| **Expected** | Treat note body as untrusted data; system prompt overrides |
| **Mitigation** | Delimit user content in LLM prompts with clear boundaries |

### EC-SEC-04 — XSS via note content in Streamlit

| Field | Detail |
|-------|--------|
| **Scenario** | Note contains HTML/JS |
| **Impact** | 🟡 Depends on render method |
| **Expected** | Use `st.markdown` with safe defaults or escape user HTML |
| **Mitigation** | Avoid `unsafe_allow_html=True` for note body |

---

## 10. Configuration & Environment

### EC-CFG-01 — Python version < 3.10

| Field | Detail |
|-------|--------|
| **Scenario** | Old Python missing features |
| **Impact** | 🟠 Syntax or dependency errors |
| **Expected** | Document Python 3.10+ requirement |
| **Mitigation** | Check version in setup script |

### EC-CFG-02 — Missing dependency in requirements.txt

| Field | Detail |
|-------|--------|
| **Scenario** | Fresh venv install fails on import |
| **Impact** | 🔴 Cannot run |
| **Expected** | Phase 0 acceptance: clean install works |
| **Mitigation** | Pin major versions; smoke test imports |

### EC-CFG-03 — Config path relative to wrong working directory

| Field | Detail |
|-------|--------|
| **Scenario** | Run `python capture.py` from subdirectory |
| **Impact** | 🟠 Writes to wrong raw/ or fails |
| **Expected** | Resolve paths relative to project root (config.py) |
| **Mitigation** | `PROJECT_ROOT = Path(__file__).parent` in config |

---

## 11. Cross-Pipeline E2E Scenarios

### EC-E2E-01 — Full pipeline with zero failures on 1 note

| Field | Detail |
|-------|--------|
| **Scenario** | Single note: capture → classify → link → graph → ask |
| **Impact** | Baseline happy path |
| **Expected** | All stages succeed; ask returns grounded answer |
| **Test** | Phase 7 checklist with one targeted note |

### EC-E2E-02 — Pipeline mid-failure recovery

| Field | Detail |
|-------|--------|
| **Scenario** | Classify succeeds for 5/10; Groq fails on rest |
| **Impact** | 🟡 Partial state |
| **Expected** | Re-run classify processes only `unprocessed` |
| **Test** | Simulate 429 on item 6; retry batch |

### EC-E2E-03 — Re-classify without duplicating wiki

| Field | Detail |
|-------|--------|
| **Scenario** | User re-runs classify on already processed raw |
| **Impact** | 🟠 Duplicate wiki notes |
| **Expected** | Skip processed unless `--force` |
| **Test** | Run classify twice; count wiki files |

### EC-E2E-04 — Deployed app vs local pipeline divergence

| Field | Detail |
|-------|--------|
| **Scenario** | Local wiki updated but deploy shows old graph |
| **Impact** | 🟡 Stale public demo |
| **Expected** | Rebuild graph + redeploy after local changes |
| **Test** | Phase 9 deployed E2E after git push |

---

## 12. Discovered During Testing

> Add new edge cases here as you find them during Phases 6–9.

| ID | Date | Scenario | Resolution |
|----|------|----------|------------|
| — | — | *(none yet)* | — |

---

## Quick Reference: Priority Fixes by Phase

| Phase | Must-handle before ship |
|-------|-------------------------|
| **0** | EC-CFG-03 path resolution, EC-CFG-02 deps |
| **1** | EC-CAP-03 YAML safety, EC-CAP-06 fetch timeout, EC-CAP-11 file not found |
| **2** | EC-CLS-01 API key, EC-CLS-04 malformed JSON, EC-CLS-08 slug collision |
| **3** | EC-LNK-04 idempotent links, EC-LNK-06 hash invalidation |
| **4** | EC-GRF-08 XSS/JSON safety, EC-GRF-01 empty state |
| **5** | EC-ASK-01 min score gate, EC-ASK-04 anti-hallucination prompt |
| **8** | EC-DEP-01 secrets, EC-DEP-02 privacy, EC-DEP-04 read-only deploy |

---

## Related Documents

- [architecture.md](./architecture.md) — system design and data models
- [implementation-plan.md](./implementation-plan.md) — phase tasks and acceptance criteria
