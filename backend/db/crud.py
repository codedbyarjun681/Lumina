from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (
    AppSetting,
    Conversation,
    ConversationMessage,
    Provider,
    Workspace,
    WorkspaceDocument,
    WorkspaceMemory,
    _new_uuid,
)
from db.schemas import (
    ConversationCreate,
    ConversationMessageCreate,
    ConversationRename,
    MemoryCreate,
    MemoryUpdate,
    WorkspaceCreate,
    WorkspaceLLMUpdate,
    WorkspaceUpdate,
)


def _require_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Name cannot be blank")
    return cleaned


def create_workspace(db: Session, data: WorkspaceCreate) -> Workspace:
    workspace = Workspace(name=_require_name(data.name))
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


def get_workspace(db: Session, workspace_id: str) -> Workspace | None:
    return db.get(Workspace, workspace_id)


def list_workspaces(db: Session) -> Sequence[Workspace]:
    stmt = select(Workspace).order_by(Workspace.created_at.asc())
    return db.execute(stmt).scalars().all()


def update_workspace(
    db: Session, workspace_id: str, data: WorkspaceUpdate
) -> Workspace | None:
    workspace = get_workspace(db, workspace_id)
    if workspace is None:
        return None
    workspace.name = _require_name(data.name)
    db.commit()
    db.refresh(workspace)
    return workspace


def update_workspace_llm(
    db: Session, workspace_id: str, data: WorkspaceLLMUpdate
) -> Workspace | None:
    workspace = get_workspace(db, workspace_id)
    if workspace is None:
        return None
    workspace.llm_provider = data.llm_provider
    workspace.llm_model = data.llm_model
    db.commit()
    db.refresh(workspace)
    return workspace


def delete_workspace(db: Session, workspace_id: str) -> bool:
    workspace = get_workspace(db, workspace_id)
    if workspace is None:
        return False
    db.delete(workspace)
    db.commit()
    return True


# ——— Conversations ———


def create_conversation(
    db: Session, workspace_id: str, data: ConversationCreate
) -> Conversation:
    conversation = Conversation(
        workspace_id=workspace_id, name=_require_name(data.name)
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def list_conversations(db: Session, workspace_id: str) -> Sequence[Conversation]:
    stmt = (
        select(Conversation)
        .where(Conversation.workspace_id == workspace_id)
        .order_by(Conversation.updated_at.desc())
    )
    return db.execute(stmt).scalars().all()


def get_conversation(db: Session, conversation_id: str) -> Conversation | None:
    return db.get(Conversation, conversation_id)


def rename_conversation(
    db: Session, conversation_id: str, data: ConversationRename
) -> Conversation | None:
    conversation = get_conversation(db, conversation_id)
    if conversation is None:
        return None
    conversation.name = _require_name(data.name)
    db.commit()
    db.refresh(conversation)
    return conversation


def delete_conversation(db: Session, conversation_id: str) -> bool:
    conversation = get_conversation(db, conversation_id)
    if conversation is None:
        return False
    stmt = select(ConversationMessage).where(
        ConversationMessage.conversation_id == conversation_id
    )
    for message in db.execute(stmt).scalars().all():
        db.delete(message)
    db.delete(conversation)
    db.commit()
    return True


# ——— Conversation messages ———


def add_message(
    db: Session, conversation_id: str, data: ConversationMessageCreate
) -> ConversationMessage:
    message = ConversationMessage(
        conversation_id=conversation_id,
        role=data.role,
        content=data.content,
    )
    db.add(message)

    # Bump the conversation's updated_at so it sorts to the top
    conversation = db.get(Conversation, conversation_id)
    if conversation is not None:
        conversation.name = conversation.name  # trigger onupdate
        db.add(conversation)

    db.commit()
    db.refresh(message)
    return message


def list_messages(
    db: Session, conversation_id: str
) -> Sequence[ConversationMessage]:
    stmt = (
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at.asc())
    )
    return db.execute(stmt).scalars().all()


def get_recent_messages(
    db: Session, conversation_id: str, limit: int
) -> Sequence[ConversationMessage]:
    stmt = (
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at.desc())
        .limit(limit)
    )
    return list(reversed(db.execute(stmt).scalars().all()))


def delete_messages_from(
    db: Session, conversation_id: str, message_id: str
) -> int | None:
    """Delete the given message and everything after it (chronologically).
    Returns the number of deleted messages, or None if the message is not
    part of the conversation."""
    messages = list(list_messages(db, conversation_id))
    ids = [m.id for m in messages]
    if message_id not in ids:
        return None
    start = ids.index(message_id)
    for message in messages[start:]:
        db.delete(message)
    db.commit()
    return len(messages) - start


# ——— Workspace documents ———


def create_document(
    db: Session,
    workspace_id: str,
    original_filename: str,
    saved_filename: str,
    file_size_bytes: int,
) -> WorkspaceDocument:
    doc = WorkspaceDocument(
        workspace_id=workspace_id,
        original_filename=original_filename,
        saved_filename=saved_filename,
        file_size_bytes=file_size_bytes,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def list_documents(db: Session, workspace_id: str) -> Sequence[WorkspaceDocument]:
    stmt = (
        select(WorkspaceDocument)
        .where(WorkspaceDocument.workspace_id == workspace_id)
        .order_by(WorkspaceDocument.uploaded_at.desc())
    )
    return db.execute(stmt).scalars().all()


def get_document(db: Session, document_id: str) -> WorkspaceDocument | None:
    return db.get(WorkspaceDocument, document_id)


def delete_document(db: Session, document_id: str) -> bool:
    doc = get_document(db, document_id)
    if doc is None:
        return False
    db.delete(doc)
    db.commit()
    return True


def get_document_by_saved_filename(
    db: Session, workspace_id: str, saved_filename: str
) -> WorkspaceDocument | None:
    stmt = select(WorkspaceDocument).where(
        WorkspaceDocument.workspace_id == workspace_id,
        WorkspaceDocument.saved_filename == saved_filename,
    )
    return db.execute(stmt).scalars().first()


def search_documents_by_filename(
    db: Session, workspace_id: str, query: str
) -> Sequence[WorkspaceDocument]:
    stmt = (
        select(WorkspaceDocument)
        .where(
            WorkspaceDocument.workspace_id == workspace_id,
            WorkspaceDocument.original_filename.ilike(f"%{query}%"),
        )
        .order_by(WorkspaceDocument.uploaded_at.desc())
    )
    return db.execute(stmt).scalars().all()


# ——— Workspace memory ———


def list_memory(db: Session, workspace_id: str) -> Sequence[WorkspaceMemory]:
    stmt = (
        select(WorkspaceMemory)
        .where(WorkspaceMemory.workspace_id == workspace_id)
        .order_by(WorkspaceMemory.updated_at.desc())
    )
    return db.execute(stmt).scalars().all()


def create_memory(
    db: Session, workspace_id: str, data: MemoryCreate, source: str
) -> WorkspaceMemory:
    entry = WorkspaceMemory(
        workspace_id=workspace_id,
        content=data.content.strip(),
        source=source,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def update_memory(
    db: Session, memory_id: str, data: MemoryUpdate
) -> WorkspaceMemory | None:
    entry = db.get(WorkspaceMemory, memory_id)
    if entry is None:
        return None
    entry.content = data.content.strip()
    db.commit()
    db.refresh(entry)
    return entry


def delete_memory(db: Session, memory_id: str) -> bool:
    entry = db.get(WorkspaceMemory, memory_id)
    if entry is None:
        return False
    db.delete(entry)
    db.commit()
    return True


# ——— Providers ———


def create_provider(
    db: Session,
    name: str,
    base_url: str,
    needs_api_key: bool,
) -> Provider:
    provider = Provider(
        id=_new_uuid(),
        name=name.strip(),
        kind="openai",
        base_url=base_url.strip(),
        needs_api_key=needs_api_key,
        is_builtin=False,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


def delete_provider(db: Session, provider_id: str) -> bool:
    provider = db.get(Provider, provider_id)
    if provider is None or provider.is_builtin:
        return False
    db.delete(provider)
    db.commit()
    return True


# ——— Conversation LLM override ———


def update_conversation_model(
    db: Session, conversation_id: str, llm_model: str, llm_provider: str | None
) -> Conversation | None:
    conversation = get_conversation(db, conversation_id)
    if conversation is None:
        return None
    conversation.llm_model = llm_model
    if llm_provider is not None:
        conversation.llm_provider = llm_provider
    db.commit()
    db.refresh(conversation)
    return conversation


def get_setting(db: Session, key: str) -> str | None:
    setting = db.get(AppSetting, key)
    return setting.value if setting else None


def set_setting(db: Session, key: str, value: str) -> AppSetting:
    setting = db.get(AppSetting, key)
    if setting is None:
        setting = AppSetting(key=key, value=value)
        db.add(setting)
    else:
        setting.value = value
    db.commit()
    db.refresh(setting)
    return setting