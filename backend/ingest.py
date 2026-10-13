import os

import chromadb
from langchain_community.document_loaders import (
    Docx2txtLoader,
    PyPDFLoader,
    UnstructuredPowerPointLoader,
)
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from embedding import get_embedding
from paths import CHROMA_ROOT_STR, DOCUMENTS_ROOT_STR


def _load_document(file_path: str):
    if file_path.endswith(".pdf"):
        loader = PyPDFLoader(file_path)
    elif file_path.endswith(".docx"):
        loader = Docx2txtLoader(file_path)
    elif file_path.endswith(".pptx"):
        loader = UnstructuredPowerPointLoader(file_path)
    else:
        return []

    docs = loader.load()

    # Tag every loaded page/chunk with the file it came from, so content
    # search and citations can map chunks back to a WorkspaceDocument row.
    for doc in docs:
        doc.metadata["source_filename"] = os.path.basename(file_path)

    return docs


def ingest_docs(workspace_id: str) -> None:
    workspace_docs_path = os.path.join(DOCUMENTS_ROOT_STR, workspace_id)
    os.makedirs(workspace_docs_path, exist_ok=True)

    # Drop the existing collection so re-indexing never duplicates chunks
    try:
        client = chromadb.PersistentClient(path=CHROMA_ROOT_STR)
        client.delete_collection(workspace_id)
    except Exception:
        pass  # collection may not exist yet on first upload

    docs = []
    for file in os.listdir(workspace_docs_path):
        file_path = os.path.join(workspace_docs_path, file)
        docs.extend(_load_document(file_path))

    if not docs:
        return  # nothing to index

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(docs)

    Chroma.from_documents(
        chunks,
        get_embedding(),
        collection_name=workspace_id,
        persist_directory=CHROMA_ROOT_STR,
    )

    print(f"Documents indexed successfully for workspace {workspace_id}")
