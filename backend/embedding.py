"""Single shared embedding model instance.

HuggingFaceEmbeddings loads a ~90MB model; instantiating it more than once
(e.g. in both ingest.py and rag.py) doubles memory usage and startup time.
Import get_embedding() everywhere instead.
"""

from __future__ import annotations

from langchain_community.embeddings import HuggingFaceEmbeddings

_embedding_instance: HuggingFaceEmbeddings | None = None


def get_embedding() -> HuggingFaceEmbeddings:
    global _embedding_instance
    if _embedding_instance is None:
        _embedding_instance = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return _embedding_instance
