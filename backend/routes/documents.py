from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from db.database import get_db
from db.schemas import DocumentOut, DocumentSearchResult
from services import document_service, workspace_service

router = APIRouter(tags=["documents"])


def _require_workspace(db: Session, workspace_id: str) -> None:
    if workspace_service.get_workspace(db, workspace_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )


@router.get(
    "/workspaces/{workspace_id}/documents",
    response_model=list[DocumentOut],
)
def list_documents(
    workspace_id: str, db: Session = Depends(get_db)
) -> list[DocumentOut]:
    _require_workspace(db, workspace_id)
    return document_service.list_documents(db, workspace_id)


@router.delete(
    "/workspaces/{workspace_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    workspace_id: str, document_id: str, db: Session = Depends(get_db)
) -> None:
    _require_workspace(db, workspace_id)
    deleted = await asyncio.to_thread(
        document_service.delete_document, db, workspace_id, document_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )


@router.get(
    "/workspaces/{workspace_id}/documents/search",
    response_model=list[DocumentSearchResult],
)
async def search_documents(
    workspace_id: str,
    q: str = Query(min_length=1),
    db: Session = Depends(get_db),
) -> list[DocumentSearchResult]:
    _require_workspace(db, workspace_id)
    hits = await asyncio.to_thread(
        document_service.search_documents, db, workspace_id, q
    )
    return [
        DocumentSearchResult(
            id=hit["doc"].id,
            original_filename=hit["doc"].original_filename,
            uploaded_at=hit["doc"].uploaded_at,
            match_type=hit["match_type"],
            excerpt=hit["excerpt"],
        )
        for hit in hits
    ]
