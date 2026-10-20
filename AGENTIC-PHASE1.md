# Agentic Lumina — Phase 1 Build Log

**Status:** In progress
**Started:** 2026-10-05

## Design (concluded in planning discussion)

**Pattern:** Orchestrator–specialist. One lightweight router decides which
specialist agent handles a message, or the user forces an agent with a
`@agent` mention.

```
User message ──► Router (1 fast LLM call or keyword fallback)
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
      ┌───────────┐          ┌───────────┐
      │  Teacher  │          │  Quiz     │
      │  agent    │          │  Master   │
      └───────────┘          └───────────┘
      tools: retrieve docs,  tools: sample chunks,
      search, memory, tutor  generate MCQ quiz
      prompt                 
```

**Key rules:**
- Per-conversation provider/model chain (conversation override → Settings
  global default → workspace legacy) applies to *every* agent step.
- Progress is streamed to the UI via SSE ("Routing…", "Retrieving documents…",
  "Generating quiz…") — this is what makes the agent feel alive instead of
  hung.
- Guardrails: fixed pipelines (no free-form agent loops), JSON-validated quiz
  output, graceful degradation.
- Persistence semantics unchanged: user + assistant messages saved to the
  conversation; memory extraction stays a post-response background task.

## Progress log

- [x] Backend agents package (router / library / orchestrator)
- [x] SSE endpoint `POST /workspaces/{id}/agent/ask`
- [x] Live stream verification (router picks correct agent per prompt)
- [x] Frontend streaming reader + progress display in chat
- [x] Build/lint + TESTING.md entry

**Status: COMPLETE** ✅

## Implementation notes

- `rag.py` refactored to expose `retrieve_with_sources()` +
  `build_tutor_prompt()` — `ask_lumina` (plain /ask) now calls them, so one
  source of truth for retrieval + prompt, zero behaviour change.
- `agents/router.py`: keyword fallback first, then one cheap LLM classify call,
  `@teacher`/`@quiz` prefixes force an agent.
- `agents/library.py`: `AgentContext` dataclass + handlers.
  - Teacher: retrieves workspace chunks → tutor prompt (with memory + history).
  - Quiz: samples chunks → `quiz_service.generate_quiz`, parses request for
    question count (regex) and difficulty word, formats markdown with an
    answer key (chats are markdown-rendered).
- `agents/orchestrator.py`: fixed pipeline — no free agent loops (guardrail).
  Emits `step` events plus an `agent` event with the chosen agent's label.
- `routes/agent.py`: SSE via `StreamingResponse`, worker thread + asyncio.Queue
  (`call_soon_threadsafe`), sentinel `__done__` event; errors become a clean
  `error` event instead of broken streams; user message persisted upfront,
  assistant persisted before the `final` event so ids ship with the result.
  Auto-title + memory extraction reuse chat.py's helpers.

## Verification results (live, against OpenRouter free models)

| Scenario | Route taken | Result |
|---|---|---|
| "What does the mitochondria produce?" | LLM classify → **Tutor** | steps streamed → answer + `cell_biology.pdf` source + message ids + auto-title ✓ |
| "quiz me with 2 questions on the mitochondria" | keyword → **Quiz Master** | parsed count=2, markdown quiz + answer key ✓ |
| "@teacher give me a one sentence summary…" | mention force → **Tutor** | mention stripped from prompt, answer returned ✓ |
| "@quiz one easy question about ATP" | mention force → **Quiz Master** | router step skipped, word-number "one" → 1 question, difficulty easy ✓ |
| Model discontinued mid-session (`apodex…:free` 404) | — | surfaced as clean `error` SSE event with the IMPROVEMENT-1 message ✓ |

Frontend: `api.askStream` (SSE reader on the `api` object), ChatSession shows
live step list during generation (pulsing latest), assistant bubbles carry an
agent badge ("Tutor" / "Quiz Master"), errors render as chat messages.
`npm run build` + `npx eslint` clean.

## Usage

- Auto: just type — router decides.
- Force: prefix a message with `@quiz` or `@teacher`.
- Quiz requests understand counts ("5 questions", "three") and difficulty
  ("easy"/"medium"/"hard").

## Next phases (not built)

- Phase 2: LangGraph graph + Reviewer role (grounding-check loop), SSE token streaming.
- Phase 3: Code agent (needs code-file ingestion + sandbox write tool), more
  specialists (planner, summarizer).
