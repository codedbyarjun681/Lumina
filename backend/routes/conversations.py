from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Conversation
from db.schemas import (
    ConversationCreate,
    ConversationLLMUpdate,
    ConversationMessageCreate,
    ConversationMessageOut,
    ConversationOut,
    ConversationRename,
)
from services import conversation_service, workspace_service
from services.export_conversation import to_markdown, to_pdf

router = APIRouter(tags=["conversations"])


def _get_conversation_or_404(
    db: Session, conversation_id: str
) -> Conversation:
    conversation = conversation_service.get_conversation(db, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return conversation


@router.get(
    "/workspaces/{workspace_id}/conversations",
    response_model=list[ConversationOut],
)
def list_conversations(
    workspace_id: str, db: Session = Depends(get_db)
) -> list[ConversationOut]:
    if workspace_service.get_workspace(db, workspace_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )
    return conversation_service.list_conversations(db, workspace_id)


@router.post(
    "/workspaces/{workspace_id}/conversations",
    response_model=ConversationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    workspace_id: str,
    data: ConversationCreate,
    db: Session = Depends(get_db),
) -> ConversationOut:
    workspace = workspace_service.get_workspace(db, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )
    try:
        # New conversations inherit the global default model if one is set,
        # otherwise the workspace's legacy default
        from services import settings_service

        prefs = settings_service.get_preferences(db)
        inherited = prefs["default_model"] or workspace.llm_model
        return conversation_service.create_conversation(
            db, workspace_id, data, default_model=inherited
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch(
    "/conversations/{conversation_id}/llm",
    response_model=ConversationOut,
)
def update_conversation_llm(
    conversation_id: str,
    data: ConversationLLMUpdate,
    db: Session = Depends(get_db),
) -> ConversationOut:
    conversation = conversation_service.update_conversation_model(
        db, conversation_id, data.llm_model, data.llm_provider
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return conversation


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationOut,
)
def rename_conversation(
    conversation_id: str,
    data: ConversationRename,
    db: Session = Depends(get_db),
) -> ConversationOut:
    try:
        conversation = conversation_service.rename_conversation(
            db, conversation_id, data
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return conversation


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)) -> None:
    deleted = conversation_service.delete_conversation(db, conversation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )


@router.delete(
    "/conversations/{conversation_id}/messages/{message_id}",
    status_code=status.HTTP_200_OK,
)
def delete_messages_from(
    conversation_id: str, message_id: str, db: Session = Depends(get_db)
) -> dict:
    """Delete a message and everything after it — used when a user edits an
    earlier prompt and the rest of the conversation regenerates."""
    _get_conversation_or_404(db, conversation_id)
    deleted = conversation_service.truncate_from_message(
        db, conversation_id, message_id
    )
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found in this conversation",
        )
    return {"deleted": deleted}


@router.get(
    "/conversations/{conversation_id}/export",
)
def export_conversation(
    conversation_id: str,
    format: str = Query(default="md", pattern="^(md|pdf)$"),
    db: Session = Depends(get_db),
) -> Response:
    conversation = _get_conversation_or_404(db, conversation_id)
    messages = conversation_service.list_messages(db, conversation_id)
    if not messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nothing to export — the conversation is empty",
        )

    safe_name = "".join(
        c if c.isalnum() or c in "-_ " else "_" for c in conversation.name
    )[:60]

    if format == "md":
        content = to_markdown(conversation.name, messages)
        return Response(
            content=content,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{safe_name or "conversation"}.md"'
                )
            },
        )

    content = to_pdf(conversation.name, messages)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{safe_name or "conversation"}.pdf"'
            )
        },
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[ConversationMessageOut],
)
def list_messages(
    conversation_id: str, db: Session = Depends(get_db)
) -> list[ConversationMessageOut]:
    _get_conversation_or_404(db, conversation_id)
    return conversation_service.list_messages(db, conversation_id)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationMessageOut,
    status_code=status.HTTP_201_CREATED,
)
def append_message(
    conversation_id: str,
    data: ConversationMessageCreate,
    db: Session = Depends(get_db),
) -> ConversationMessageOut:
    _get_conversation_or_404(db, conversation_id)
    return conversation_service.append_message(db, conversation_id, data)
