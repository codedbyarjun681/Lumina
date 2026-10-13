from __future__ import annotations

from sqlalchemy.orm import Session

from db import crud
from db.models import Conversation, ConversationMessage
from db.schemas import (
    ConversationCreate,
    ConversationMessageCreate,
    ConversationRename,
)


def list_conversations(db: Session, workspace_id: str) -> list[Conversation]:
    return list(crud.list_conversations(db, workspace_id))


def create_conversation(
    db: Session,
    workspace_id: str,
    data: ConversationCreate,
    default_model: str | None = None,
) -> Conversation:
    conversation = crud.create_conversation(db, workspace_id, data)
    if default_model:
        conversation.llm_model = default_model
        db.commit()
        db.refresh(conversation)
    return conversation


def update_conversation_model(
    db: Session, conversation_id: str, llm_model: str, llm_provider: str | None = None
) -> Conversation | None:
    return crud.update_conversation_model(db, conversation_id, llm_model, llm_provider)


def get_conversation(db: Session, conversation_id: str) -> Conversation | None:
    return crud.get_conversation(db, conversation_id)


def rename_conversation(
    db: Session, conversation_id: str, data: ConversationRename
) -> Conversation | None:
    return crud.rename_conversation(db, conversation_id, data)


def delete_conversation(db: Session, conversation_id: str) -> bool:
    return crud.delete_conversation(db, conversation_id)


def list_messages(
    db: Session, conversation_id: str
) -> list[ConversationMessage]:
    return list(crud.list_messages(db, conversation_id))


def append_message(
    db: Session, conversation_id: str, data: ConversationMessageCreate
) -> ConversationMessage:
    return crud.add_message(db, conversation_id, data)


def get_recent_history(
    db: Session, conversation_id: str, limit: int = 6
) -> list[dict[str, str]]:
    messages = crud.get_recent_messages(db, conversation_id, limit)
    return [{"role": m.role, "content": m.content} for m in messages]


def truncate_from_message(
    db: Session, conversation_id: str, message_id: str
) -> int | None:
    return crud.delete_messages_from(db, conversation_id, message_id)
