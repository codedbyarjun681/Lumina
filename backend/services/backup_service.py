"""Workspace export/import — portable archives for backup and sharing.

Archive layout (zip):
    workspace.json   — workspace, conversations + messages, memory entries,
                       document metadata (original/saved filenames)
    documents/…      — the raw uploaded files

ChromaDB is intentionally NOT included: it is a derived index, rebuilt by
re-ingestion on import. This keeps archives portable across machines and
Chroma versions.
"""

from __future__ import annotations

import io
import json
import zipfile

from sqlalchemy.orm import Session

from db import crud
from db.models import Workspace
from ingest import ingest_docs
from paths import DOCUMENTS_ROOT


def export_workspace(db: Session, workspace: Workspace) -> bytes:
    conversations = crud.list_conversations(db, workspace.id)
    payload = {
        "format_version": 1,
        "workspace": {
            "name": workspace.name,
            "llm_provider": workspace.llm_provider,
            "llm_model": workspace.llm_model,
        },
        "conversations": [
            {
                "name": c.name,
                "llm_model": c.llm_model,
                "llm_provider": c.llm_provider,
                "messages": [
                    {"role": m.role, "content": m.content}
                    for m in crud.list_messages(db, c.id)
                ],
            }
            for c in conversations
        ],
        "memory": [
            {"content": m.content, "source": m.source}
            for m in crud.list_memory(db, workspace.id)
        ],
        "documents": [
            {
                "original_filename": d.original_filename,
                "saved_filename": d.saved_filename,
                "file_size_bytes": d.file_size_bytes,
            }
            for d in crud.list_documents(db, workspace.id)
        ],
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("workspace.json", json.dumps(payload, indent=2))
        docs_dir = DOCUMENTS_ROOT / workspace.id
        if docs_dir.is_dir():
            for file in docs_dir.iterdir():
                if file.is_file():
                    zf.write(file, f"documents/{file.name}")
    return buffer.getvalue()


def import_workspace(db: Session, archive: bytes) -> Workspace:
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        payload = json.loads(zf.read("workspace.json"))
        doc_files: dict[str, bytes] = {}
        for name in zf.namelist():
            if name.startswith("documents/") and not name.endswith("/"):
                doc_files[name.split("/", 1)[1]] = zf.read(name)

    from db.schemas import WorkspaceCreate

    workspace = crud.create_workspace(
        db, WorkspaceCreate(name=payload["workspace"]["name"])
    )
    workspace.llm_provider = payload["workspace"].get("llm_provider", "ollama")
    workspace.llm_model = payload["workspace"].get("llm_model", "qwen3:8b")
    db.commit()
    db.refresh(workspace)

    # Restore documents (fresh UUID saved filenames to avoid collisions)
    docs_dir = DOCUMENTS_ROOT / workspace.id
    docs_dir.mkdir(parents=True, exist_ok=True)

    import uuid as _uuid

    for meta in payload.get("documents", []):
        content = doc_files.get(meta.get("saved_filename", ""))
        if content is None:
            continue
        ext = ""
        original = meta.get("original_filename", "file")
        if "." in meta.get("saved_filename", ""):
            ext = "." + meta["saved_filename"].rsplit(".", 1)[1]
        elif "." in original:
            ext = "." + original.rsplit(".", 1)[1]
        saved = f"{_uuid.uuid4()}{ext}"
        (docs_dir / saved).write_bytes(content)
        crud.create_document(
            db,
            workspace.id,
            original_filename=original,
            saved_filename=saved,
            file_size_bytes=len(content),
        )

    # Restore memory
    from db.schemas import MemoryCreate

    for entry in payload.get("memory", []):
        crud.create_memory(
            db,
            workspace.id,
            MemoryCreate(content=entry.get("content", "")),
            source=entry.get("source", "manual"),
        )

    # Restore conversations + messages (fresh ids)
    from db.schemas import ConversationCreate

    for conv in payload.get("conversations", []):
        conversation = crud.create_conversation(
            db,
            workspace.id,
            ConversationCreate(name=conv.get("name", "Imported conversation")),
        )
        for msg in conv.get("messages", []):
            from db.schemas import ConversationMessageCreate

            crud.add_message(
                db,
                conversation.id,
                ConversationMessageCreate(
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                ),
            )

    # Rebuild the vector index from the restored documents
    if any((docs_dir).iterdir()):
        ingest_docs(workspace.id)

    return workspace
