from __future__ import annotations

import shutil

import chromadb
from sqlalchemy.orm import Session

from db import crud
from db.models import Workspace
from db.schemas import WorkspaceCreate, WorkspaceLLMUpdate, WorkspaceUpdate
from paths import CHROMA_ROOT_STR, DOCUMENTS_ROOT


def create_workspace(db: Session, data: WorkspaceCreate) -> Workspace:
    return crud.create_workspace(db, data)


def get_workspace(db: Session, workspace_id: str) -> Workspace | None:
    return crud.get_workspace(db, workspace_id)


def list_workspaces(db: Session) -> list[Workspace]:
    return list(crud.list_workspaces(db))


def rename_workspace(
    db: Session, workspace_id: str, data: WorkspaceUpdate
) -> Workspace | None:
    return crud.update_workspace(db, workspace_id, data)


def update_workspace_llm(
    db: Session, workspace_id: str, data: WorkspaceLLMUpdate
) -> Workspace | None:
    return crud.update_workspace_llm(db, workspace_id, data)


def delete_workspace(db: Session, workspace_id: str) -> bool:
    deleted = crud.delete_workspace(db, workspace_id)
    if not deleted:
        return False

    # Clean up uploaded documents on disk
    shutil.rmtree(DOCUMENTS_ROOT / workspace_id, ignore_errors=True)

    # Drop the workspace's ChromaDB collection
    try:
        client = chromadb.PersistentClient(path=CHROMA_ROOT_STR)
        client.delete_collection(workspace_id)
    except Exception:
        pass

    return True