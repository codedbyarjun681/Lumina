from __future__ import annotations

import zipfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from db.database import get_db
from db.schemas import (
    WorkspaceCreate,
    WorkspaceLLMUpdate,
    WorkspaceOut,
    WorkspaceUpdate,
)
from services import backup_service, workspace_service

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
def create_workspace(
    data: WorkspaceCreate, db: Session = Depends(get_db)
) -> WorkspaceOut:
    try:
        return workspace_service.create_workspace(db, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=list[WorkspaceOut])
def list_workspaces(db: Session = Depends(get_db)) -> list[WorkspaceOut]:
    return workspace_service.list_workspaces(db)


@router.get("/{workspace_id}", response_model=WorkspaceOut)
def get_workspace(workspace_id: str, db: Session = Depends(get_db)) -> WorkspaceOut:
    workspace = workspace_service.get_workspace(db, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )
    return workspace


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
def rename_workspace(
    workspace_id: str, data: WorkspaceUpdate, db: Session = Depends(get_db)
) -> WorkspaceOut:
    try:
        workspace = workspace_service.rename_workspace(db, workspace_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )
    return workspace


@router.patch("/{workspace_id}/llm-settings", response_model=WorkspaceOut)
def update_workspace_llm(
    workspace_id: str, data: WorkspaceLLMUpdate, db: Session = Depends(get_db)
) -> WorkspaceOut:
    workspace = workspace_service.update_workspace_llm(db, workspace_id, data)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )
    return workspace


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(workspace_id: str, db: Session = Depends(get_db)) -> None:
    deleted = workspace_service.delete_workspace(db, workspace_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )


@router.get("/{workspace_id}/export")
def export_workspace(workspace_id: str, db: Session = Depends(get_db)) -> Response:
    workspace = workspace_service.get_workspace(db, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )
    archive = backup_service.export_workspace(db, workspace)
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in workspace.name)
    return Response(
        content=archive,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="lumina-{safe_name or "workspace"}.zip"'
            )
        },
    )


@router.post("/import", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
async def import_workspace(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> WorkspaceOut:
    archive = await file.read()
    try:
        return backup_service.import_workspace(db, archive)
    except (KeyError, ValueError, zipfile.BadZipFile) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Not a valid Lumina workspace archive: {e}",
        )