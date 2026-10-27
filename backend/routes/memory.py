from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db.database import get_db
from db.schemas import MemoryCreate, MemoryOut, MemoryUpdate
from services import memory_service, workspace_service

router = APIRouter(tags=["memory"])


@router.get(
    "/workspaces/{workspace_id}/memory",
    response_model=list[MemoryOut],
)
def list_memory(
    workspace_id: str, db: Session = Depends(get_db)
) -> list[MemoryOut]:
    if workspace_service.get_workspace(db, workspace_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )
    return memory_service.list_memory(db, workspace_id)


@router.post(
    "/workspaces/{workspace_id}/memory",
    response_model=MemoryOut,
    status_code=status.HTTP_201_CREATED,
)
def create_memory(
    workspace_id: str,
    data: MemoryCreate,
    db: Session = Depends(get_db),
) -> MemoryOut:
    workspace = workspace_service.get_workspace(db, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )
    if data.conversation_id is not None:
        from services import conversation_service

        conversation = conversation_service.get_conversation(
            db, data.conversation_id
        )
        if conversation is None or conversation.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="conversation_id does not belong to this workspace",
            )
    return memory_service.create_memory(db, workspace_id, data, source="manual")


@router.patch("/memory/{memory_id}", response_model=MemoryOut)
def update_memory(
    memory_id: str, data: MemoryUpdate, db: Session = Depends(get_db)
) -> MemoryOut:
    entry = memory_service.update_memory(db, memory_id, data)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Memory entry not found"
        )
    return entry


@router.delete("/memory/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(memory_id: str, db: Session = Depends(get_db)) -> None:
    deleted = memory_service.delete_memory(db, memory_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Memory entry not found"
        )
