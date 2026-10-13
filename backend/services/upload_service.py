from __future__ import annotations

import os
import uuid

from sqlalchemy.orm import Session

from db import crud
from db.models import WorkspaceDocument
from ingest import ingest_docs
from paths import DOCUMENTS_ROOT

ALLOWED_EXTENSIONS = [".pdf", ".docx", ".pptx"]


class UnsupportedFileTypeError(Exception):
    def __init__(self, extension: str) -> None:
        self.extension = extension
        super().__init__(f"Unsupported file type: {extension}")


def save_file(
    file_content: bytes,
    original_filename: str,
    workspace_id: str,
    db: Session,
) -> WorkspaceDocument:
    """Write the file to disk and record it in the DB. No indexing."""
    extension = os.path.splitext(original_filename or "")[1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError(extension)

    workspace_docs_path = DOCUMENTS_ROOT / workspace_id
    workspace_docs_path.mkdir(parents=True, exist_ok=True)

    # Server-generated filename: prevents path traversal and collisions
    saved_filename = f"{uuid.uuid4()}{extension}"
    file_path = workspace_docs_path / saved_filename

    with open(file_path, "wb") as f:
        f.write(file_content)

    return crud.create_document(
        db,
        workspace_id,
        original_filename=original_filename or saved_filename,
        saved_filename=saved_filename,
        file_size_bytes=len(file_content),
    )


def save_and_index_file(
    file_content: bytes,
    original_filename: str,
    workspace_id: str,
    db: Session,
) -> WorkspaceDocument:
    """Save a single file, then re-index the whole workspace."""
    document = save_file(file_content, original_filename, workspace_id, db)
    ingest_docs(workspace_id)
    return document
