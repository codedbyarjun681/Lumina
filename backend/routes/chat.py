from __future__ import annotations

import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import SessionLocal, get_db
from db.schemas import ConversationMessageCreate, ConversationRename
from services import (
    conversation_service,
    memory_service,
    settings_service,
    workspace_service,
)
from services.provider_service import get_provider
from services.rag_service import get_answer

router = APIRouter(tags=["chat"])


def _auto_title(text: str) -> str:
    cleaned = text.strip().rstrip("?!.,;:")
    if len(cleaned) <= 50:
        return cleaned
    truncated = cleaned[:50]
    last_space = truncated.rfind(" ")
    return truncated[:last_space] if last_space > 0 else truncated


class QuestionRequest(BaseModel):
    question: str
    workspace_id: str
    conversation_id: str


def _run_memory_extraction(
    question: str,
    answer: str,
    workspace_id: str,
    provider: str,
    model: str,
    api_key: str | None,
) -> None:
    """Runs in the background after /ask has already responded."""
    from rag import extract_memory

    try:
        facts = extract_memory(question, answer, provider, model, api_key)
    except Exception:
        return

    if not facts:
        return

    # The request-scoped session is closed by now — open a fresh one.
    db = SessionLocal()
    try:
        memory_service.save_extracted_facts(db, workspace_id, facts)
    finally:
        db.close()


@router.post("/ask")
async def ask_question(
    request: QuestionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    workspace = workspace_service.get_workspace(db, request.workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )

    conversation = conversation_service.get_conversation(
        db, request.conversation_id
    )
    if conversation is None or conversation.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found in this workspace",
        )

    # Resolution chain: conversation override → global default (Settings) → workspace
    effective_provider, effective_model = settings_service.resolve_llm(
        db,
        conversation.llm_provider,
        conversation.llm_model,
        workspace.llm_provider,
        workspace.llm_model,
    )

    api_key = None
    provider_config = get_provider(effective_provider, db)
    if provider_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown LLM provider: {effective_provider}",
        )
    if provider_config.needs_api_key:
        api_key = settings_service.get_api_key(db, effective_provider)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Provider {provider_config.name} has no API key configured "
                    "in Settings."
                ),
            )

    # First message in this conversation? Then auto-title afterwards.
    is_first_message = (
        len(conversation_service.list_messages(db, conversation.id)) == 0
    )

    user_message = conversation_service.append_message(
        db,
        conversation.id,
        ConversationMessageCreate(role="user", content=request.question),
    )

    memory_entries = memory_service.get_prompt_memory(
        db, workspace.id, conversation.id
    )
    history = conversation_service.get_recent_history(db, conversation.id, limit=6)

    rag_result = await asyncio.to_thread(
        get_answer,
        request.question,
        request.workspace_id,
        effective_provider,
        effective_model,
        api_key,
        memory_entries,
        history,
        db,
    )
    answer = rag_result["answer"]
    sources = rag_result["sources"]

    assistant_message = conversation_service.append_message(
        db,
        conversation.id,
        ConversationMessageCreate(role="assistant", content=answer),
    )

    result = {
        "response": answer,
        "sources": sources,
        "user_message_id": user_message.id,
        "assistant_message_id": assistant_message.id,
    }

    if is_first_message:
        renamed = conversation_service.rename_conversation(
            db, conversation.id, ConversationRename(name=_auto_title(request.question))
        )
        if renamed is not None:
            result["conversation_name"] = renamed.name

    background_tasks.add_task(
        _run_memory_extraction,
        request.question,
        answer,
        workspace.id,
        effective_provider,
        effective_model,
        api_key,
    )

    return result
