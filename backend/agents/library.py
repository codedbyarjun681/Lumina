"""Specialist agent definitions.

Each agent is a (definition, handler) pair. Handlers run synchronously on a
worker thread; they report progress through ctx.emit(...) which forwards into
the SSE stream, and return a dict with at least {"answer": str, ...}.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from agents import reviewer as reviewer_agent
from rag import _get_llm, _llm_text, build_tutor_prompt, retrieve_with_sources


@dataclass
class AgentContext:
    question: str
    workspace_id: str
    provider: str
    model: str
    api_key: str | None
    memory_entries: list[str]
    conversation_history: list[dict]
    db: object
    emit: Callable[[dict], None] = field(default=lambda e: None, repr=False)


@dataclass
class Agent:
    id: str
    label: str
    handle: Callable[[AgentContext], dict]


def _stream_llm_text(llm, prompt: str, provider: str, model: str, emit) -> str:
    """Invoke the LLM token-by-token, emitting {"event":"token"} per chunk.
    Falls back to a single non-streaming call if streaming breaks before the
    first token. Returns the full text."""
    pieces: list[str] = []
    try:
        for chunk in llm.stream(prompt):
            token = chunk.content if hasattr(chunk, "content") else str(chunk)
            if not token:
                continue
            pieces.append(token)
            emit({"event": "token", "text": token})
    except Exception as e:
        if not pieces:
            # Nothing streamed yet — safe to fall back to a plain call
            text = _llm_text(llm, prompt, provider, model)
            emit({"event": "token", "text": text})
            return text
        raise  # mid-stream failure: surface it (route turns it into an error event)
    return "".join(pieces)


# ——— Teacher agent ———


def _teacher_run(ctx: AgentContext) -> dict:
    ctx.emit({"event": "step", "label": "Searching the workspace's documents…"})
    docs, sources = retrieve_with_sources(ctx.question, ctx.workspace_id, ctx.db)
    context = (
        "\n\n".join(doc.page_content for doc in docs)
        if docs
        else "No relevant documents found."
    )

    llm = _get_llm(ctx.provider, ctx.model, ctx.api_key)
    feedback: list[str] | None = None

    for round_index in range(1, reviewer_agent.REVIEW_MAX_ROUNDS + 1):
        if round_index == 1:
            ctx.emit({"event": "step", "label": "Composing your answer…"})
        else:
            # Clear the streamed draft before the revision begins
            ctx.emit({"event": "restart"})
            ctx.emit(
                {
                    "event": "step",
                    "label": f"Revising (attempt {round_index}) with reviewer feedback…",
                }
            )

        prompt = build_tutor_prompt(
            ctx.question, context, ctx.memory_entries, ctx.conversation_history
        )
        if feedback:
            prompt += (
                "\n\nA reviewer flagged issues with your previous attempt — fix them:\n"
                + "\n".join(f"- {issue}" for issue in feedback)
                + "\n\nAnswer again:\n"
            )
        answer = _stream_llm_text(llm, prompt, ctx.provider, ctx.model, ctx.emit)

        if round_index < reviewer_agent.REVIEW_MAX_ROUNDS:
            ctx.emit({"event": "step", "label": "Reviewing answer for grounding…"})
            verdict = reviewer_agent.review_answer(
                ctx.question,
                context,
                answer,
                ctx.provider,
                ctx.model,
                ctx.api_key,
                round_index,
            )
            if verdict["verdict"] == "grounded":
                break
            feedback = verdict["issues"] or ["The draft was not grounded in the context."]
        else:
            # Last round: accept whatever we have (guardrail against loops)
            break

    return {"answer": answer, "sources": sources}


TEACHER = Agent(id="teacher", label="Tutor", handle=_teacher_run)


# ——— Quiz agent ———

_NUMBER_RE = re.compile(r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\b")
_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_DIFFICULTY_WORDS = {"easy", "medium", "hard"}
_DEFAULT_QUESTIONS = 5
_DEFAULT_DIFFICULTY = "medium"


def _quiz_run(ctx: AgentContext) -> dict:
    from services import quiz_service

    low = ctx.question.lower()
    num_match = _NUMBER_RE.search(low)
    if num_match:
        token = num_match.group(1)
        count = _WORD_NUMBERS.get(token, None) if not token.isdigit() else int(token)
        num_questions = min(20, max(1, count)) if count else _DEFAULT_QUESTIONS
    else:
        num_questions = _DEFAULT_QUESTIONS
    difficulty = next(
        (w for w in _DIFFICULTY_WORDS if w in low), _DEFAULT_DIFFICULTY
    )

    ctx.emit(
        {
            "event": "step",
            "label": "Sampling key content from the workspace's documents…",
        }
    )
    questions = quiz_service.generate_quiz(
        ctx.workspace_id,
        ctx.provider,
        ctx.model,
        ctx.api_key,
        num_questions,
        difficulty,
    )

    # Persist so attempts can be scored and history kept
    from services import quiz_history_service

    saved = quiz_history_service.save_quiz(
        ctx.db, ctx.workspace_id, questions, difficulty
    )

    ctx.emit({"event": "step", "label": "Formatting your quiz…"})
    lines = [f"### Quiz — {len(questions)} question(s) · {difficulty}", ""]
    answer_key: list[str] = []
    for i, q in enumerate(questions, 1):
        lines.append(f"**{i}. {q['question']}**")
        for letter in "ABCD":
            lines.append(f"- **{letter}.** {q['options'][letter]}")
        lines.append("")
        answer_key.append(f"{i}. **{q['correct']}** — {q['explanation']}")
    lines.append("---")
    lines.append("#### Answer key")
    lines.extend(answer_key)
    return {
        "answer": "\n".join(lines),
        "sources": [],
        "quiz": {"quiz_id": saved.id, "questions": questions},
    }


QUIZ = Agent(id="quiz", label="Quiz Master", handle=_quiz_run)


AGENTS: dict[str, Agent] = {a.id: a for a in (TEACHER, QUIZ)}
