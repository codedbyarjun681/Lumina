from __future__ import annotations

from sqlalchemy.orm import Session

from db import crud
from db.models import WorkspaceMemory
from db.schemas import MemoryCreate, MemoryUpdate

MEMORY_PROMPT_LIMIT = 10


def list_memory(db: Session, workspace_id: str) -> list[WorkspaceMemory]:
    return list(crud.list_memory(db, workspace_id))


def create_memory(
    db: Session, workspace_id: str, data: MemoryCreate, source: str = "manual"
) -> WorkspaceMemory:
    return crud.create_memory(db, workspace_id, data, source)


def update_memory(
    db: Session, memory_id: str, data: MemoryUpdate
) -> WorkspaceMemory | None:
    return crud.update_memory(db, memory_id, data)


def delete_memory(db: Session, memory_id: str) -> bool:
    return crud.delete_memory(db, memory_id)


def get_prompt_memory(
    db: Session, workspace_id: str, conversation_id: str | None = None
) -> list[str]:
    """Conversation-scoped entries first, then workspace-global ones, capped."""
    entries = crud.list_memory(db, workspace_id)
    scoped = [
        e for e in entries if conversation_id and e.conversation_id == conversation_id
    ]
    global_ = [e for e in entries if e.conversation_id is None]
    combined = scoped + global_
    return [entry.content for entry in combined[:MEMORY_PROMPT_LIMIT]]


def save_extracted_facts(
    db: Session, workspace_id: str, facts: list[str]
) -> None:
    for fact in facts:
        text = fact.strip()
        if text:
            crud.create_memory(
                db, workspace_id, MemoryCreate(content=text), source="auto"
            )
