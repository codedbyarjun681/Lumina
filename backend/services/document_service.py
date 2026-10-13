from __future__ import annotations

from sqlalchemy.orm import Session

from db import crud
from db.models import WorkspaceDocument
from embedding import get_embedding
from paths import CHROMA_ROOT_STR, DOCUMENTS_ROOT


def list_documents(db: Session, workspace_id: str) -> list[WorkspaceDocument]:
    return list(crud.list_documents(db, workspace_id))


def delete_document(db: Session, workspace_id: str, document_id: str) -> bool:
    doc = crud.get_document(db, document_id)
    if doc is None or doc.workspace_id != workspace_id:
        return False

    saved_filename = doc.saved_filename
    deleted = crud.delete_document(db, document_id)
    if not deleted:
        return False

    # Remove the file from disk
    file_path = DOCUMENTS_ROOT / workspace_id / saved_filename
    file_path.unlink(missing_ok=True)

    # Re-index only if files remain
    folder = DOCUMENTS_ROOT / workspace_id
    if folder.exists() and any(folder.iterdir()):
        from ingest import ingest_docs

        ingest_docs(workspace_id)

    return True


def _content_search(db: Session, workspace_id: str, query: str) -> list[dict]:
    """Search chunk embeddings; map chunks back to documents by filename."""
    try:
        from langchain_community.vectorstores import Chroma

        store = Chroma(
            collection_name=workspace_id,
            persist_directory=CHROMA_ROOT_STR,
            embedding_function=get_embedding(),
        )
        chunks = store.similarity_search(query, k=5)
    except Exception:
        return []  # collection may not exist yet

    results = []
    seen: set[str] = set()
    for chunk in chunks:
        saved_filename = chunk.metadata.get("source_filename")
        if not saved_filename or saved_filename in seen:
            continue
        doc = crud.get_document_by_saved_filename(db, workspace_id, saved_filename)
        if doc is None:
            continue
        seen.add(saved_filename)
        results.append({"doc": doc, "excerpt": chunk.page_content[:200]})
    return results


def search_documents(db: Session, workspace_id: str, query: str) -> list[dict]:
    by_filename = crud.search_documents_by_filename(db, workspace_id, query)
    by_content = _content_search(db, workspace_id, query)

    merged: dict[str, dict] = {}

    for doc in by_filename:
        merged[doc.id] = {"doc": doc, "match_type": "filename", "excerpt": None}

    for hit in by_content:
        doc = hit["doc"]
        if doc.id in merged:
            merged[doc.id]["match_type"] = "both"
            merged[doc.id]["excerpt"] = hit["excerpt"]
        else:
            merged[doc.id] = {
                "doc": doc,
                "match_type": "content",
                "excerpt": hit["excerpt"],
            }

    return list(merged.values())
