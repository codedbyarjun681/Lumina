from __future__ import annotations

import json

from fastapi import HTTPException
from langchain_community.vectorstores import Chroma

from embedding import get_embedding
from paths import CHROMA_ROOT_STR
from rag import _get_llm, _llm_text

SAMPLE_QUERY = "key concepts definitions important facts explanations"
SAMPLE_CHUNK_COUNT = 20


def _build_prompt(topic_context: str, num_questions: int, difficulty: str) -> str:
    return f"""You are a quiz generator. Generate exactly {num_questions} multiple-choice questions
based ONLY on the content below. Difficulty level: {difficulty}.

Each question must have exactly 4 options labeled A, B, C, D, exactly one correct
answer, and a one-sentence explanation of why the answer is correct.

Return ONLY a valid JSON array with no preamble, no markdown fences, no extra text.
Each array element must have this exact shape:
{{"question": "...", "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
"correct": "A", "explanation": "..."}}

Content:
{topic_context}"""


def _parse_questions(raw: str) -> list[dict]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[len("json"):].strip()
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []

    questions = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        options = item.get("options")
        correct = item.get("correct")
        if (
            not item.get("question")
            or not isinstance(options, dict)
            or not all(k in options for k in "ABCD")
            or correct not in "ABCD"
        ):
            continue
        questions.append(
            {
                "question": str(item["question"]),
                "options": {k: str(options[k]) for k in "ABCD"},
                "correct": str(correct),
                "explanation": str(item.get("explanation", "")),
            }
        )
    return questions


def generate_quiz(
    workspace_id: str,
    provider: str,
    model: str,
    api_key: str | None,
    num_questions: int,
    difficulty: str,
) -> list[dict]:
    try:
        store = Chroma(
            collection_name=workspace_id,
            persist_directory=CHROMA_ROOT_STR,
            embedding_function=get_embedding(),
        )
        chunks = store.similarity_search(SAMPLE_QUERY, k=SAMPLE_CHUNK_COUNT)
    except Exception:
        chunks = []

    if not chunks:
        raise HTTPException(
            status_code=422,
            detail=(
                "No documents are indexed for this workspace — "
                "upload documents first."
            ),
        )

    context = "\n\n".join(chunk.page_content for chunk in chunks)
    llm = _get_llm(provider, model, api_key)
    raw = _llm_text(
        llm, _build_prompt(context, num_questions, difficulty), provider, model
    )

    questions = _parse_questions(raw)[:num_questions]
    if not questions:
        raise HTTPException(
            status_code=422,
            detail="The model did not return a valid quiz. Please try again.",
        )
    return questions
