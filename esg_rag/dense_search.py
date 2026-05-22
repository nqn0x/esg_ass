"""
esg_rag/dense_search.py
-----------------------
dense_search(query, k=30, filters=None) -> list[SearchHit]

Embeds the query via Albert then does cosine similarity search in Qdrant.
Good at:
  - Paraphrased concepts: "carbon footprint" matches "GHG emissions"
  - Conceptual questions: "how does X manage climate risk"
  - Cross-lingual (bge-m3 is multilingual)
"""

from __future__ import annotations

import esg_rag.albert as albert
from esg_rag.schemas import SearchHit
from esg_rag.store import QdrantStore
from esg_rag.store import get_store

_store: QdrantStore | None = None


def _get_store() -> QdrantStore:
    global _store
    if _store is None:
        _store = QdrantStore()
    return _store

def dense_search(query, k=30, filters=None, doc_ids=None):
    vecs = albert.embed_texts([query[:800]], caller="dense_search")
    store = get_store()
    hits = store.search_dense(vecs[0], top_k=k, doc_ids=doc_ids, filters=filters)
    for i, h in enumerate(hits):
        h.rank = i + 1
        h.search_type = "dense"
    return hits
