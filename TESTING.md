# Lumina — Audit & Test Log

## BUG-1 Duplicate ingestion

**Status:** PASS
**Date:** 2026-09-11

**What was checked:**
- `backend/ingest.py` — deletes the existing ChromaDB collection before re-indexing (lines 40–45)
- Uses `get_embedding()` from `embedding.py` (line 60) — no direct `HuggingFaceEmbeddings` instantiation
- Every loaded document tagged with `metadata["source_filename"] = os.path.basename(file_path)` (lines 28–31)

**Test results:**
- Created workspace `1db5cd6a-c21b-4278-8b7e-fb41f01ba99b` ("BUG1-Test")
- `POST /upload` with `doc1.pdf` → `{"message":"File uploaded and indexed successfully"}`; chunk count = **1**
- `POST /upload` with `doc2.pdf` → success; chunk count = **2** (not 3 or 4 — doc1 was NOT re-duplicated)
- Unique `source_filename` values in collection metadata: 2 UUID basenames, matching the two uploaded files

**Issues found:**
- None

**Action taken:**
- None — already correct

## BUG-2 Double embedding model load

**Status:** PASS
**Date:** 2026-09-11

**What was checked:**
- `backend/embedding.py` exists, exports lazy singleton `get_embedding()`
- Grep of entire backend for `HuggingFaceEmbeddings(` — only match is `embedding.py:18`
- `rag.py` line 85 uses `embedding_function=get_embedding()`; `ingest.py` line 60 uses `get_embedding()`
- Neither file references `HuggingFaceEmbeddings` at all (grep count = 0 in both)

**Test results:**
- `grep -rn "HuggingFaceEmbeddings(" --include="*.py"` excluding venv → single hit: `embedding.py`
- Module-level embedding instantiation removed from both `rag.py` and `ingest.py` — model loads lazily on first use, once

**Issues found:**
- None

**Action taken:**
- None — already correct

## BUG-3 Blocking event loop

**Status:** PASS
**Date:** 2026-09-11

**What was checked:**
- `routes/chat.py` line 122: `answer = await asyncio.to_thread(get_answer, ...)`
- `routes/upload.py` line 70: `save_and_index_file` wrapped in `asyncio.to_thread`; line 96: batch processing also wrapped
- Both endpoints are `async def` and read upload bytes on the event loop, offloading disk write + indexing + LLM calls to threads

**Test results:**
- Fired `POST /upload` (PDF + full workspace re-index with embedding model CPU work) in the background
- Simultaneously called `GET /` → responded `{"message":"Lumina Backend Running"}` in **7ms** — no blocking
- Upload completed normally: `{"message":"File uploaded and indexed successfully"}`

**Issues found:**
- None

**Action taken:**
- None — already correct

## BUG-4 Unhandled errors

**Status:** PASS
**Date:** 2026-09-11

**What was checked:**
- `rag.py` `_llm_text()` (lines 40–54): catches exceptions; "connection refused"/"could not connect" → `HTTPException(503, human-readable)`; other errors → `HTTPException(500, str(e))`
- `db/crud.py` `_require_name()` (line 30) applied to workspace create (38), workspace rename (60), conversation create (95), conversation rename (122); routes catch `ValueError` → 400

**Test results:**
- `/ask` on workspace with provider=ollama while Ollama down → `503 {"detail":"LLM provider is unreachable — check that Ollama or LM Studio is running, or verify network access."}` ✓
- Non-connection error (OpenRouter rate limit 429) → `500` with the provider's message in `detail` ✓
- `POST /workspaces {"name":"   "}` → `400 {"detail":"Name cannot be blank"}` ✓
- `PATCH /conversations/{id} {"name":"  "}` → `400 {"detail":"Name cannot be blank"}` ✓

**Issues found:**
- None

**Action taken:**
- None — already correct

## FEAT-1 Workspace deletion cleanup

**Status:** PASS
**Date:** 2026-09-11

**What was checked:**
- `services/workspace_service.py` `delete_workspace()`: calls `crud.delete_workspace`, then `shutil.rmtree(DOCUMENTS_ROOT / workspace_id, ignore_errors=True)`, then drops the Chroma collection via `chromadb.PersistentClient(path=CHROMA_ROOT_STR)` wrapped in try/except

**Test results:**
- Before: `documents/` contained folder `1db5cd6a-...` (BUG1 test ws); Chroma had 4 collections including both test workspaces
- `DELETE /workspaces/1db5cd6a-...` → 204; `DELETE /workspaces/...bug4-ws...` → 204
- After: `documents/` no longer contains either test folder; Chroma collections list no longer contains either workspace ID

**Issues found:**
- None (note: one loose legacy PDF from the pre-UUID-filenames era sits directly in `documents/` — harmlessly outside any workspace folder)

**Action taken:**
- None — already correct


## FEAT-2 Document tracking

**Status:** PASS
**Date:** 2026-09-11

**What was checked:**
- `db/models.py` — `WorkspaceDocument` model with `id` (UUID PK), `workspace_id`, `original_filename`, `saved_filename`, `file_size_bytes`, `uploaded_at`
- `services/upload_service.py` line 44 — `save_file()` calls `crud.create_document(...)` capturing original filename, UUID saved filename, and `file_size_bytes=len(file_content)` before any UUID-ification
- `services/document_service.py` — `list_documents`, `delete_document`, `_content_search`, `search_documents`

**Test results:**
- Earlier live upload tests (BUG-1/BUG-3) produced `WorkspaceDocument` rows queryable via `GET /workspaces/{id}/documents` — verified in FEAT-3 test below
- Model columns match the required schema exactly

**Issues found:**
- None

**Action taken:**
- None — already correct

## FEAT-3 Recent documents panel

**Status:** PASS
**Date:** 2026-10-02

**What was checked:**
- `routes/documents.py`: `GET /workspaces/{id}/documents` (ordered by `uploaded_at` desc, line 26), `DELETE /workspaces/{id}/documents/{doc_id}` (line 37, threaded via asyncio.to_thread)
- `services/document_service.py` delete: removes DB row, `file_path.unlink(missing_ok=True)` from disk, re-indexes via `ingest_docs` only when remaining files exist
- `api.ts`: `fetchDocuments` (line 148), `deleteDocument` (line 152) on the `api` object
- `App.tsx`: "Workspace Documents" SidePanel (line 491), documents fetched on open (356), sidebar footer button wired via `onDocumentsClick` (420)

**Test results:**
- Created workspace, uploaded doc1.pdf + doc2.pdf
- `GET .../documents` → 2 rows, newest first (`uploaded_at` desc verified), correct original filenames + sizes
- Files on disk: 2 UUID-named PDFs ✓
- `DELETE .../documents/{doc2_id}` → 204; after: 1 row, 1 file on disk, Chroma chunk count 2→1 (re-indexed with remaining file)

**Issues found:**
- None

**Action taken:**
- None — already correct

## FEAT-4 Drag-and-drop and multi-file uploads

**Status:** PASS
**Date:** 2026-10-02

**What was checked:**
- `routes/upload.py`: `POST /upload/batch` (line 84) accepts `workspace_id` + `files: list[UploadFile]`; `_process_batch` (line 21) processes sequentially, per-file try/except, calls `ingest_docs` **once** at the end (line 48) guarded by try/except; offloaded via `asyncio.to_thread` (line 96)
- `ChatSession.tsx`: `onDragOver`/`onDragLeave`/`onDrop` (229–231), `drag-overlay` div (249), extension filter `.pdf/.docx/.pptx` (15, 211), `handleFileSelected(files: File | File[])` (155) routing single → `uploadFile`, multi → `uploadBatch` (140)
- `api.ts`: `uploadBatch` (line 133)

**Test results:**
- `POST /upload/batch` with doc1.pdf + doc2.pdf + bad.exe → `{"results":[{"filename":"doc1.pdf","success":true,"message":"Uploaded"},{"filename":"doc2.pdf","success":true,"message":"Uploaded"},{"filename":"bad.exe","success":false,"message":"Unsupported file type"}]}`
- Batch did NOT abort on the bad file; Chroma chunk count = 2 (one re-index, correct content)

**Issues found:**
- None

**Action taken:**
- None — already correct

## FEAT-5 Document search

**Status:** PASS
**Date:** 2026-10-02

**What was checked:**
- `routes/documents.py`: `GET /workspaces/{id}/documents/search?q=...` (line 54, `Query(min_length=1)`, threaded)
- `services/document_service.py`: filename arm via SQLAlchemy `ilike` + content arm via Chroma similarity search with `get_embedding()`; maps chunks→documents via `metadata["source_filename"]`→`saved_filename`; merges with dedupe producing `filename` | `content` | `both`; content arm wrapped in try/except → empty list
- `api.ts` `searchDocuments`; App.tsx debounced 300ms search input (line 395), match badges (567), excerpt rendering (572)

**Test results:**
- Uploaded `cell_biology.pdf` + `plants101.pdf`
- Search `q=cell` → `cell_biology.pdf` match_type=**both** (filename + content) with excerpt; `plants101.pdf` content (semantic match) ✓
- Search `q=photosynthesis` → `plants101.pdf` content-first with excerpt ✓
- Search on workspace with NO Chroma collection → `[]` HTTP 200 (no crash) ✓

**Issues found:**
- None

**Action taken:**
- None — already correct

## POLISH-1 Markdown rendering in chat bubbles

**Status:** PASS
**Date:** 2026-10-02

**What was checked:**
- `react-markdown@^10.1.0` in `lumina-desktop/package.json` dependencies
- `ChatArea.tsx` line 48: assistant bubbles render `<ReactMarkdown>{message.content}</ReactMarkdown>`; user bubbles render plain string (line 49–51 ternary)
- `App.css`: 20 `.markdown-body` selector rules covering h1–h4, p, ul/ol, li, strong, em, inline code, pre blocks, blockquote, links — all contained within bubble padding (max-width already inherited)

**Test results:**
- `npm run build` (includes tsc) passes with ReactMarkdown — 185 modules transformed, no errors
- Visual browser test not executable in this environment; code path is a direct conditional render

**Issues found:**
- None

**Action taken:**
- None — already correct

## POLISH-2 Conversation auto-titling

**Status:** PASS
**Date:** 2026-10-02

**What was checked:**
- `chat.py`: `_auto_title()` (line 23) — strips trailing punctuation, truncates to 50 chars at last word boundary
- `is_first_message` detection before persisting the user message (line 109); rename via `rename_conversation` (141–143); response includes `conversation_name` only when auto-titling occurred (146)
- Frontend: `ChatSession.tsx` reads `result.conversation_name` and calls `applyConversationName` on the store (113–116); `api.ts` `AskResult.conversation_name?` typed (line 12)

**Test results:**
- New conversation named "New Conversation"; sent first message "In simple terms, what does the mitochondria do inside a cell?" via `/ask` (OpenRouter free model)
- Response `{response, conversation_name: "In simple terms, what does the mitochondria do"}` ✓
- Subsequent `GET /workspaces/{id}/conversations` shows the renamed conversation ✓
- Later messages did NOT re-trigger renaming (rename only fires when message count was 0)

**Issues found:**
- None

**Action taken:**
- None — already correct

## BACKLOG-1 Quiz generation

**Status:** IMPLEMENTED
**Date:** 2026-10-02

**What was checked:**
- Previously: no quiz code existed anywhere in the repo (verified by grep — only third-party library matches)

**Test results:**
- Backend: new `services/quiz_service.py` (Chroma sample of 20 chunks via generic concept query, strict-JSON prompt, fence-stripping + shape-validating parser, HTTP 422 on parse failure or empty collection); new `routes/quiz.py` (`POST /workspaces/{id}/quiz` — `num_questions` 1–20, difficulty easy|medium|hard, provider key resolution, `asyncio.to_thread`); registered in `app.py`
- Live: empty workspace → `422 {"detail":"No documents are indexed for this workspace — upload documents first."}` ✓
- Live: after uploading `cell_biology.pdf`, generated 2 easy questions via OpenRouter free model — both well-formed (A–D options, correct key, explanation, grounded in document content) ✓
- Frontend: `types/Quiz.ts`, `api.generateQuiz`, `components/QuizPanel.tsx` (setup → loading → playing → done; green/red reveal + correct answer; Next; score summary; Retake reshuffle; New Quiz; no-workspace / zero-document guards), sidebar "Quiz" footer button wired to SidePanel in App.tsx, full `.quiz-*` CSS

**Issues found:**
- None

**Action taken:**
- Implemented fully (backend + frontend)

## BACKLOG-2 Citations and sources

**Status:** IMPLEMENTED
**Date:** 2026-10-02

**What was checked:**
- Previously: `/ask` returned only `{response, conversation_name?}`; no source tracking existed

**Test results:**
- Backend: `rag.py` `ask_lumina` now returns `{"answer": str, "sources": [...]}` and accepts a `db` param; sources built from chunk `metadata["source_filename"]` → `crud.get_document_by_saved_filename` → `original_filename`, deduplicated per file with first/closest chunk's 150-char excerpt; `rag_service.py` and `routes/chat.py` updated to pass `db` and unpack the dict; `/ask` response now `{response, sources, conversation_name?}` (also switched chat + memory-extraction paths to `effective_model` per-conversation override)
- Live: `/ask` on a workspace containing `cell_biology.pdf` returned `keys: [response, sources]` with `sources=[('cell_biology.pdf', 'The mitochondria is the powerhouse of the cell. It...')]` ✓
- Frontend: `Message.sources?: MessageSource[]` in types; `AskResult.sources` in api.ts; `ChatSession` attaches sources to the assistant message; `ChatArea` renders a collapsible "📄 N sources" section (collapsed by default, per-source filename + excerpt cards); `.sources-*` CSS added and contained within bubble layout

**Issues found:**
- `return` type annotation of `/ask` handler was still `dict[str, str]` after adding the sources list — fixed to `dict`
- Memory-extraction background call was still using `workspace.llm_model` instead of the conversation's `effective_model` — fixed (bonus correctness fix)

**Action taken:**
- Implemented fully (backend + frontend)

## IMPROVEMENT-1 Provider error handling (409/403) + OpenRouter attribution headers

**Status:** IMPLEMENTED
**Date:** 2026-10-02

**What was checked:**
- Previously: `rag.py:_llm_text` dumped raw provider exceptions as `HTTPException(500, str(e))` — users saw "Error code: 409 - {...}" blobs. OpenRouter requests carried no app attribution headers.
- Root cause: langchain-openai raises `openai.APIStatusError`-shaped exceptions whose string form embeds the provider's error code and a single-quoted JSON-ish payload.

**Test results:**
- Unit: `_friendly_llm_error` mapped all 10 shapes correctly — 409→clean congestion notice, 403→"built for agentic interfaces, pick a different model", 429→rate-limit guidance, 401→check-key-in-Settings, 404→model unavailable, 400→provider detail passthrough, 500→502 upstream wrapper, timeout→504, connection refused→503, unknown→500 with truncated detail
- Live 400: bogus model `totally/bogus-model:free` → `400 {"detail":"The provider rejected the request (provider said: totally/bogus-model:free is not a valid model ID)"}` ✓
- Live 401: temporary custom provider (real OpenRouter base URL) with dummy key → `401 Authentication failed — the API key for ERR-Test-Prov is invalid or expired… (provider said: Missing Authentication header)` ✓
- Headers: `_get_llm('openrouter', …)` attaches `default_headers: {'HTTP-Referer','X-Title'}`; LM Studio unaffected (None) ✓

**Issues found:**
- `ApiKeyUpdate` schema still restricted provider ids to `openrouter|opencode` → setting API keys for custom providers returned 422. Fixed (now `min_length=1, max_length=50`). This was a real bug from the custom-provider feature.
- All `_llm_text` call sites (`ask_lumina`, `extract_memory`, `quiz_service.generate_quiz`) updated to pass provider+model for clean error attribution.

**Action taken:**
- Implemented `_friendly_llm_error` + OpenRouter attribution headers in `rag.py`; updated 3 call sites; fixed `ApiKeyUpdate` schema; cleaned up all test workspaces/providers/keys; frontend build+lint clean.

## IMPROVEMENT-2 Theme system + Settings redesign + per-conversation provider/model

**Status:** IMPLEMENTED
**Date:** 2026-10-02

**What was checked/implemented:**
- Backend: `PUT /settings/preferences` for theme/colorway/default_provider/default_model (stored in `app_settings` with `pref:` prefix); `conversations.llm_provider` column + migration; shared resolver `resolve_llm(conversation → global default → workspace legacy)` used by both `/ask` and `/quiz`; `/conversations/{id}/llm` now accepts provider+model
- Frontend: `theme.ts` (light/dark/system + 8 colorways), system listener via `matchMedia`, CSS colorway blocks for all themes; Settings panel now contains Appearance (Light/Dark/System buttons + colorway popover), Model defaults, Workspaces (create/rename/delete moved in from the old Workspace Manager panel), Providers (list + add/delete custom), API keys, and a local-model detection banner
- Sidebar: removed dedicated Workspace Manager panel; "+ Workspace" opens Settings
- ModelPicker: two-step (provider list filtered to usable providers — no key configured providers hidden — then models); per-conversation overrides write provider+model

**Test results:**
- Preference round-trip: PUT + GET returned `{theme:dark, colorway:cocoa, default_provider:openrouter, default_model:apodex-1.1-mini:free}` ✓
- New conversation with null override answered via global default (OpenRouter/apodex) — resolution chain works ✓
- Conversation PATCHed to `anthropic` (no key) → clean error "Provider Anthropic has no API key configured in Settings." — proves the override actually switches provider ✓
- `npm run build` + `npx eslint` clean

**Issues found:**
- Test conversations ("fallback test", "override test") cleaned up after verification

**Action taken:**
- Implemented fully (backend + frontend)

## IMPROVEMENT-3 Collapsible sidebar + chat message actions (edit/copy)

**Status:** IMPLEMENTED
**Date:** 2026-10-04

**What was checked:**
- ChatArea previously rendered plain bubbles with no actions — confirmed absent
- Backend had no message edit/delete capability — messages could only be appended

**Test results:**
- New backend capability: `crud.delete_messages_from` + route `DELETE /conversations/{conversation_id}/messages/{message_id}` — truncated from a specific message + everything after; verified live: 3 messages → delete from 2nd → `{"deleted":2}`, remaining `['m1']`; bad message id → `404 Message not found in this conversation`
- `/ask` now returns `user_message_id` + `assistant_message_id` (verified live — response keys: response, sources, conversation_name, user_message_id, assistant_message_id)
- Frontend: user bubbles show ✎ (pencil, edit) + ⧉ (copy) on hover; assistant bubbles show ⧉ copy; edit opens inline textarea resizable with Save & resend (⌘/Ctrl+Enter works) / Cancel (Esc), which truncates the conversation on the server, drops the old thread locally, and re-asks
- If server truncation fails, the UI refuses to re-ask on top of an un-truncated conversation (defensive guard) and shows a reload notice
- Copy uses `navigator.clipboard` with a 1.2 s ✓ confirmation tick
- Sidebar: `‹` button in the logo row collapses the panel (smooth width/overflow animation with `.sidebar-inner` holding a fixed min width so text doesn't reflow mid-animation), and a floating ☰ "Open sidebar" button appears at the top-left of the main area; state persists across launches via `localStorage` (`lumina:sidebar`)

**Issues found:**
- None

**Action taken:**
- Implemented fully (backend + frontend); `npm run build` + `npx eslint` clean

## FEATURE Agentic Phase 1 — router + Tutor/Quiz agents with SSE streaming

**Status:** IMPLEMENTED
**Date:** 2026-10-05

**What was checked:**
- No agentic code existed before this build

**Test results:**
- Backend: `agents/` package (router with keyword→LLM→fallback classification, `@teacher`/`@quiz` force mentions; Tutor agent reusing RAG retrieval + tutor prompt; Quiz Master agent wrapping quiz_service with word/digit count + difficulty parsing); `rag.py` refactored to share `retrieve_with_sources`/`build_tutor_prompt` with zero `/ask` behaviour change; new SSE route `POST /workspaces/{id}/agent/ask` (worker thread → asyncio.Queue → StreamingResponse; errors stream as clean `error` events; persistence + auto-title + memory extraction identical to `/ask`)
- Live verified (real OpenRouter models): LLM-routed tutor answer (with sources + ids + auto-title) ✓; keyword-routed quiz (count=2 parsed) ✓; `@teacher` force with mention stripping ✓; `@quiz` force skips router step and parses "one easy question" → 1 question/easy ✓; discontinued-model 404 surfaced as a friendly SSE error ✓
- Frontend: `api.askStream` SSE reader (fetch stays on the api object), live step-list progress with pulsing current step, agent badge on assistant bubbles ("Tutor"/"Quiz Master"), rate-limit/unreachable errors rendered as chat messages; `npm run build` + `npx eslint` clean
- Test conversations cleaned up afterwards

**Issues found:**
- Conversation created before a global-default change kept its stale inherited model — expected resolution-chain behaviour, resolved by the per-conversation picker
- Word-numbers ("one"…"ten") not parsed initially — fixed

**Action taken:**
- Implemented fully; documented in AGENTIC-PHASE1.md

## FEATURE-1+2 Workspace export / import (backup + share)

**Status:** IMPLEMENTED
**Date:** 2026-10-06

**What was checked:**
- No backup or sharing capability existed

**Test results:**
- New `services/backup_service.py`: export builds an in-memory zip (`workspace.json` + raw `documents/`); ChromaDB deliberately excluded — it is a derived index, rebuilt on import (archives stay portable across machines/Chroma versions)
- `GET /workspaces/{id}/export` — live: exported real "ML Ops" workspace → 200, 3.7 KB zip containing workspace.json + cell_biology PDF; JSON verified: 3 conversations / 18 messages / 12 memory entries / 1 document ✓
- `POST /workspaces/import` — live: re-imported the archive → new workspace with all conversations (renamed titles intact), documents (fresh UUID filenames), 12 memory entries; Chroma collection re-embedded (1 chunk); content search on the imported workspace returns `cell_biology.pdf` ✓
- Invalid archive → clean `400 Not a valid Lumina workspace archive` ✓ (initially 500 — fixed by catching `zipfile.BadZipFile`)
- Frontend: Settings → Workspaces gained an "Export" button per workspace (blob download) and "Import workspace…" (hidden file input); api.ts gained `exportWorkspace`/`importWorkspace`. Build + lint clean

**Issues found:**
- Missing `Response`/`File`/`zipfile` imports after edits — fixed during test round

**Action taken:**
- Implemented fully; test-imported workspace deleted afterwards

## FEATURE-3 Conversation export (Markdown / PDF)

**Status:** IMPLEMENTED
**Date:** 2026-10-06

**Test results:**
- New `services/export_conversation.py` + route `GET /conversations/{id}/export?format=md|pdf`
- Live: MD export → 200, 3.4 KB, correct "# title / **You**: / **Lumina**:" structure ✓
- Live: PDF export → 200, valid PDF 1.3, 3 pages (fpdf2; DejaVu font when present, latin-1 sanitize fallback otherwise) ✓
- Empty conversation → clean 400 "Nothing to export" ✓
- Frontend: conversation hover actions gained ⤓ (Markdown) and ⎙ (PDF) download buttons; `api.exportConversation` blob-download
- `fpdf2` added to requirements.txt

**Issues found:**
- fpdf2 ≥2.5 `multi_cell` defaults `new_x=RIGHT`, leaving the cursor at the right margin → next full-width cell gets ~zero width ("Not enough horizontal space") — fixed by passing `new_x=LMARGIN, new_y=NEXT` on every cell (root-caused via minimal repro)

**Action taken:**
- Implemented fully; build + lint clean

## FEATURE-4 Quiz persistence (saved quizzes + attempt history)

**Status:** IMPLEMENTED
**Date:** 2026-10-06

**Test results:**
- New `quizzes` + `quiz_attempts` tables (via `create_all`), crud + `quiz_history_service`, routes: POST quiz now saves + returns `quiz_id`; `GET /workspaces/{id}/quizzes` (list w/ best/last/attempts); `GET/DELETE /quizzes/{id}`; `POST /quizzes/{id}/attempts`
- Live: generate → saved with id ✓; list shows n/difficulty ✓; attempt 2/2 → best=2 last=2 ✓; attempt 1/2 → best=2 last=1 attempts=2 ✓; score>total → 400 ✓; delete → 204 then 404 (attempts cascade) ✓
- Frontend: QuizPanel gained a "Saved quizzes" history section (retake/delete/best-score badges), generated quizzes auto-saved, panel completions record attempts

**Issues found:**
- None

**Action taken:**
- Implemented fully

## FEATURE-5 Interactive quiz cards in chat

**Status:** IMPLEMENTED
**Date:** 2026-10-06

**Test results:**
- Quiz agent now persists every generated quiz and returns `quiz: {quiz_id, questions}` in the SSE final event (live: `@quiz two easy questions…` → final event carried quiz_id + 2 structured questions ✓)
- New shared `QuizCard` component (pick→reveal green/red→next→score; Retake reshuffles; New Quiz hook); ChatArea renders QuizCard instead of markdown when a message carries `quiz`; completing a chat quiz records the attempt against the saved quiz (live: 2/2 → best=2 attempts=1 ✓); QuizPanel playing phase reuses QuizCard
- Build + lint clean (fixed a prop-mutation bug — `setQuestions` on a prop — by moving shuffling into internal state)

**Issues found:**
- Initial QuizCard draft mutated props; caught by type-check review and fixed with internal shuffled state

**Action taken:**
- Implemented fully; test quizzes + conversations cleaned up afterwards

## FEATURE-6 Regenerate reply button

**Status:** IMPLEMENTED
**Date:** 2026-10-06

**Test results:**
- Assistant bubbles now show ↻ on hover (next to copy); clicking truncates the conversation from the originating user prompt server-side (existing `DELETE …/messages/{id}` machinery), removes the stale tail locally, and re-asks the same question — fresh answer + fresh sources
- Guards: disabled while loading; if the originating prompt isn't persisted (no id), a chat notice explains instead of failing silently
- Build + lint clean

**Issues found:**
- None

**Action taken:**
- Implemented (frontend only — backend truncation + re-ask already existed)

## FEATURE-7 Deeper citations (page numbers)

**Status:** IMPLEMENTED
**Date:** 2026-10-06

**Test results:**
- `retrieve_with_sources` now reads chunk `metadata["page"]` (set by PyPDFLoader during ingest) and emits 1-based `page` per source; DOCX/PPTX simply omit it
- Live: `/ask` on the PDF workspace returned source `('cell_biology.pdf', page 1)` ✓
- Frontend: sources cards show "cell_biology.pdf · p. 1"; types extended (`MessageSource.page?`)

**Issues found:**
- None

**Action taken:**
- Implemented fully

## FEATURE-8 Document viewer panel

**Status:** IMPLEMENTED
**Date:** 2026-10-06

**Test results:**
- New route `GET /workspaces/{id}/documents/{doc_id}/file` → FileResponse (application/pdf for PDFs, octet-stream otherwise, Content-Disposition with original filename)
- Live: fetched the workspace's PDF → 200, 1089 bytes, valid PDF ✓; bogus id → 404 ✓; missing-on-disk guarded
- Frontend: Documents panel shows 👁 "View PDF" on PDFs → full-area preview overlay (iframe + close), non-PDFs keep delete-only
- Build + lint clean

**Issues found:**
- None

**Action taken:**
- Implemented fully

## FEATURE-9 Onboarding flow

**Status:** IMPLEMENTED
**Date:** 2026-10-06

**Test results:**
- Main area renders a "Welcome to Lumina" card (name input + Create + explanation) when the workspace list has loaded and is empty; creating from it lands the user straight in their new workspace
- `bootstrapped` flag prevents the card flashing for users who DO have workspaces (waits for the first `loadWorkspaces`)
- True-fresh-install verified by running an isolated backend (`LUMINA_DATA_DIR` override): `/workspaces` → `[]`, providers still seeded (5) — exactly the onboarding state

**Issues found:**
- First "fresh" test served real data — root cause: the legacy `backend/{data,chroma_db,documents}` migration leftovers still existed, so the new instance auto-migrated them (legacy migration working as designed). Deleted the leftovers as part of this feature (they were on the tech-debt list); fresh installs now genuinely start empty

**Action taken:**
- Implemented; bonus cleanup of 5MB legacy folders

## FEATURE-10 Per-conversation memory scoping

**Status:** IMPLEMENTED
**Date:** 2026-10-06

**Test results:**
- `workspace_memory.conversation_id` nullable column + migration; `MemoryCreate`/`MemoryOut` extended
- `get_prompt_memory(db, ws, conversation_id)` — scoped entries first, then workspace-global, capped at 10; used by both `/ask` and the agentic endpoint
- Live: scoped memory created with conversation_id ✓; global with null ✓; foreign conversation_id → 400 ✓; resolution: target conversation sees [scoped, global], other conversations see global only ✓
- Frontend: Memory panel "Only this conversation" checkbox (disabled without an active conversation); scoped entries show a "chat" badge

**Issues found:**
- None

**Action taken:**
- Implemented fully; test entries cleaned up

## FEATURE-11 Drag-reorder workspaces

**Status:** IMPLEMENTED
**Date:** 2026-10-20

**Test results:**
- `workspaces.position` column + migration; `list_workspaces` ordered by position→created_at; `PUT /workspaces/reorder {ids}` assigns positions
- Live: reorder persisted (positions 0/1 written, GET reflected new order); restored afterwards
- Frontend: sidebar workspace rows are HTML5-draggable with a hover ⠿ grip; optimistic store reorder + server persist
- Build + lint clean

**Issues found (data hygiene, both fixed):**
- The F1/F2 import test left a duplicate "ML Ops" workspace in the real DB — its cleanup command had read a wiped temp file and silently no-opped. Deleted the artifact; user's original workspace untouched
- `delete_workspace` did NOT cascade — deleted workspaces left orphaned conversations/messages/documents/quizzes/memory rows (proven by earlier artifacts). Fixed: full cascade in `crud.delete_workspace`; live-verified zero orphans after deleting the duplicate (rows, Chroma collection, and documents folder all gone)

**Action taken:**
- Implemented fully + cascade-delete hardening

## FEATURE Agentic Phase 2 — Reviewer grounding loop + token streaming

**Status:** IMPLEMENTED
**Date:** 2026-10-20

**Test results:**
- New `agents/reviewer.py`: strict LLM grounding verdict (JSON, fence-tolerant parse), **fail-open** on any reviewer failure; `LUMINA_FORCE_REVIEW_RETRY=1` env hook for end-to-end loop testing
- Tutor pipeline upgraded: retrieve → draft (**streamed token-by-token**) → review → conditional revise (feedback injected into prompt, `restart` event clears the UI draft); hard cap `REVIEW_MAX_ROUNDS=2`; streaming falls back to a single call if `.stream` fails before the first token
- LangGraph deliberately deferred (rationale documented in AGENTIC-PHASE2.md) — pipeline is graph-shaped plain orchestration; adopt LangGraph when ≥3 agents run per request
- Live (normal): 63 token events; steps incl. "Reviewing answer for grounding…"; streamed text == final answer exactly; 0 restarts ✓
- Live (forced retry): restart event fired once; "Revising (attempt 2) with reviewer feedback…" step; revised draft streamed and **byte-identical to the final response (204/204 chars)** ✓
- Frontend: `onToken`/`onRestart` in api.askStream; ChatSession `streamText` state; ChatArea renders a live streaming bubble with pulsing caret (plain text while streaming, markdown at final); steps card hides when tokens start
- Build + lint clean; test conversations cleaned up; server restored without the forced-retry env

**Issues found:**
- None (initial string-equality "mismatch" in the retry test was a test-harness splice artifact, disproven by exact comparison)

**Action taken:**
- Implemented fully; documented in AGENTIC-PHASE2.md
