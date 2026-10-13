from __future__ import annotations

from rag import ask_lumina


def get_answer(
    question: str,
    workspace_id: str,
    provider: str,
    model: str,
    api_key: str | None,
    memory_entries: list[str] | None = None,
    conversation_history: list[dict] | None = None,
    db=None,
) -> dict:
    return ask_lumina(
        question,
        workspace_id,
        provider,
        model,
        api_key,
        memory_entries,
        conversation_history,
        db,
    )
