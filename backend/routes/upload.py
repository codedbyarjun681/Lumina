from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from db.database import get_db
from ingest import ingest_docs
from services import workspace_service
from services.upload_service import (
    UnsupportedFileTypeError,
    save_and_index_file,
    save_file,
)

router = APIRouter(tags=["upload"])


def _process_batch(
    items: list[tuple[str, bytes]], workspace_id: str, db: Session
) -> list[dict]:
    results = []
    for filename, content in items:
        try:
            save_file(content, filename, workspace_id, db)
            results.append(
                {"filename": filename, "success": True, "message": "Uploaded"}
            )
        except UnsupportedFileTypeError:
            results.append(
                {
                    "filename": filename,
                    "success": False,
                    "message": "Unsupported file type",
                }
            )
        except Exception as e:
            results.append(
                {"filename": filename, "success": False, "message": str(e)}
            )

    # Re-index once per batch, never once per file. A file that fails to
    # parse must not fail the whole batch.
    if any(r["success"] for r in results):
        try:
            ingest_docs(workspace_id)
        except Exception as e:
            print(f"Warning: re-indexing workspace {workspace_id} failed: {e}")

    return results


@router.post("/upload")
async def upload_file(
    workspace_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if workspace_service.get_workspace(db, workspace_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )

    content = await file.read()
    filename = file.filename or "unnamed"

    try:
        await asyncio.to_thread(
            save_and_index_file, content, filename, workspace_id, db
        )
    except UnsupportedFileTypeError:
        return JSONResponse(
            content={"error": "Unsupported file type"},
            status_code=400,
        )

    return JSONResponse(
        content={"message": "File uploaded and indexed successfully"}
    )


@router.post("/upload/batch")
async def upload_batch(
    workspace_id: str = Form(...),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if workspace_service.get_workspace(db, workspace_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )

    items = [(f.filename or "unnamed", await f.read()) for f in files]
    results = await asyncio.to_thread(_process_batch, items, workspace_id, db)

    return JSONResponse(content={"results": results})
