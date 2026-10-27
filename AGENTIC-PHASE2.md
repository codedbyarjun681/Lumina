# Agentic Lumina — Phase 2 Build Log

**Status:** In progress
**Started:** 2026-10-20

## Scope (from the concluded roadmap)

Phase 2 upgrades the Tutor pipeline from "retrieve → answer" to a
**draft → review → revise loop**, and makes answers stream token-by-token:

```
retrieve chunks ──► draft (STREAMED) ──► reviewer (grounding verdict)
                          ▲                    │
                          │              grounded │ needs_work (round < max)
                          └──── revise (STREAMED) ◄── + issues feedback
```

- **Reviewer**: a strict second LLM pass judges whether the draft is grounded
  in the retrieved context and actually answers the question.
- **Retry loop**: `needs_work` → regenerate with the reviewer's issues
  appended to the prompt. Max rounds = 2 (draft + 1 revision) by default.
- **Fail-open**: if the reviewer itself errors or returns unparseable output,
  the draft is accepted — the pipeline never blocks the user because its own
  quality gate broke.
- **Token streaming**: drafts/revisions stream live; a `restart` SSE event
  tells the UI to clear the streamed text when a revision begins.

## Design decision — LangGraph deferred (deliberate)

The Phase-1 plan sketched "LangGraph" for Phase 2. After weighing it against
the actual Phase-2 shape, the pipeline is **graph-structured plain
orchestration** instead:

- The graph here is one conditional edge (draft → review → revise|done).
  LangGraph's value — cycles, branching, checkpointing, parallel fan-out —
  earns its dependency cost in Phase 3 (planner + parallel specialists), not
  yet.
- Token streaming bypasses any graph executor anyway (tokens flow straight
  from the LLM to SSE), and our thread + queue plumbing already works.
- The node structure is explicit data in `agents/library.py`; swapping the
  executor for LangGraph later is mechanical, not a rewrite.

Revisit trigger for adopting LangGraph: when ≥3 specialist agents run in a
single request or nodes need parallel fan-out.

## Progress log

- [x] `agents/reviewer.py` — grounding verdict, fence-tolerant JSON parse, fail-open
- [x] Token-streaming helper + Tutor pipeline loop
- [x] Frontend streaming bubble + restart handling
- [x] Live SSE verification (normal + forced-retry path via `LUMINA_FORCE_REVIEW_RETRY`)

**Status: COMPLETE** ✅

## Verification results (live, real LLM calls)

| Scenario | Expected | Result |
|---|---|---|
| Normal tutor question | tokens stream → review → grounded → final | 63 token events; steps: search → compose → **review**; streamed text == final answer byte-for-byte; 0 restarts ✓ |
| `LUMINA_FORCE_REVIEW_RETRY=1` | draft → review flags → `restart` → revised draft → final | steps show "Revising (attempt 2) with reviewer feedback…"; 1 restart event; second draft streamed; **exact splice match with final (204/204 chars)** ✓ |
| Frontend | streaming bubble with caret, restart clears it | `npm run build` + `npx eslint` clean; token/restart handlers wired in `api.ts` → `ChatSession` → `ChatArea` |

**Guardrails shipped:**
- `REVIEW_MAX_ROUNDS = 2` (draft + one revision) — loop can never run away
- Reviewer fail-open: reviewer errors/unparseable output accept the draft
- Streaming fallback: if `.stream` fails before the first token, single non-streaming call instead
- Mid-stream failures surface as clean SSE `error` events (existing route plumbing)

**Known notes:**
- Reviewer uses the conversation's resolved provider/model — same chain as the tutor
- Token events are per-chunk (~60–100/request); if remote clients ever feel chatty, micro-batching is a future optimization
- Test conversations cleaned up afterwards; server restored to normal (no forced-retry env)
