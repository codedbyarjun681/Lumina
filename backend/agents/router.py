"""Intent router for the agentic pipeline.

Deterministic keyword rules fire first (fast, free, reliable); if nothing
matches, one cheap LLM call classifies the question. LLM failure falls back
to the teacher agent. Users can override entirely with a @mention.
"""

from __future__ import annotations

QUIZ_KEYWORDS = (
    "quiz",
    "test me",
    "practice questions",
    "practice question",
    "exam",
    "mcq",
    "multiple choice",
    "assess me",
)

FORCEABLE = {"teacher", "quiz"}


def force_agent(question: str) -> str | None:
    """'@quiz generate 3 questions' → 'quiz'; '@teacher why...' → 'teacher'."""
    text = question.strip()
    if text.startswith("@"):
        head = text[1:].split(None, 1)[0].lower()
        if head in FORCEABLE:
            return head
    return None


def strip_mention(question: str) -> str:
    text = question.strip()
    if text.startswith("@"):
        parts = text.split(None, 1)
        return parts[1] if len(parts) > 1 else ""
    return text


def keyword_classify(question: str) -> str | None:
    low = question.lower()
    for kw in QUIZ_KEYWORDS:
        if kw in low:
            return "quiz"
    return None


def llm_classify(
    question: str, provider: str, model: str, api_key: str | None
) -> str | None:
    from rag import _get_llm, _llm_text

    prompt = f"""Classify the user's intent into exactly one of these agents:
- teacher: questions about the workspace's documents, explanations, summarising, tutoring
- quiz: the user wants to be tested, quizzed, or wants practice questions generated

Reply with exactly one word: teacher or quiz

User message: {question}"""
    try:
        raw = _llm_text(_get_llm(provider, model, api_key), prompt, provider, model)
    except Exception:
        return None
    answer = raw.strip().lower().strip(".,!\"'")
    return answer if answer in FORCEABLE else None


def classify(
    question: str, provider: str, model: str, api_key: str | None
) -> str:
    forced = force_agent(question)
    if forced is not None:
        return forced
    via_keywords = keyword_classify(question)
    if via_keywords is not None:
        return via_keywords
    via_llm = llm_classify(question, provider, model, api_key)
    if via_llm is not None:
        return via_llm
    return "teacher"
