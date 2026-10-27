"""Reviewer agent — grounding gate for the Tutor pipeline.

A strict second LLM pass judges whether a draft answer is actually grounded
in the retrieved context and addresses the question. Fail-open by design: any
reviewer error or unparseable output accepts the draft, so the quality gate
can never hard-block the user.

`LUMINA_FORCE_REVIEW_RETRY=1` (server env) forces a `needs_work` verdict on
the first round — a test hook for exercising the revise loop end-to-end.
"""

from __future__ import annotations

import json
import os

from rag import _get_llm, _llm_text

REVIEW_MAX_ROUNDS = 2  # draft + one revision


def _parse_verdict(raw: str) -> dict | None:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[len("json"):].strip()
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    verdict = parsed.get("verdict")
    if verdict not in ("grounded", "needs_work"):
        return None
    issues = parsed.get("issues", [])
    if not isinstance(issues, list):
        issues = [str(issues)]
    return {
        "verdict": verdict,
        "issues": [str(i) for i in issues if i][:5],
    }


def review_answer(
    question: str,
    context: str,
    draft: str,
    provider: str,
    model: str,
    api_key: str | None,
    round_index: int = 1,
) -> dict:
    """Returns {"verdict": "grounded"|"needs_work", "issues": [...]}. Fail-open."""
    if os.environ.get("LUMINA_FORCE_REVIEW_RETRY") and round_index == 1:
        return {
            "verdict": "needs_work",
            "issues": ["(forced test verdict) the draft misses a detail from the context"],
        }

    prompt = f"""You are a strict reviewer for a RAG tutor. Given the user's question, the
retrieved context, and a draft answer, judge whether the draft answer:
1. is fully grounded in the context (no fabricated facts, nothing asserted beyond it), and
2. actually addresses the question.

Return ONLY valid JSON, no preamble, no markdown fences:
{{"verdict": "grounded" | "needs_work", "issues": ["short issue description", ...]}}

User's question:
{question}

Retrieved context:
{context}

Draft answer:
{draft}"""

    try:
        llm = _get_llm(provider, model, api_key)
        raw = _llm_text(llm, prompt, provider, model)
    except Exception:
        return {"verdict": "grounded", "issues": []}  # fail-open

    parsed = _parse_verdict(raw)
    if parsed is None:
        return {"verdict": "grounded", "issues": []}  # fail-open
    return parsed
