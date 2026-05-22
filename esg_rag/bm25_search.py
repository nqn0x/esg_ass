"""
esg_rag/bm25_search.py
----------------------
bm25_search(query, k=30, filters=None) -> list[SearchHit]

Wraps Qdrant sparse (BM25) search. Good at:
  - Exact terms: "Scope 1", "ESRS E1", tickers, fiscal years
  - Acronyms, standard names, precise numbers
  - Complementing dense search (which misses exact matches)
"""

from __future__ import annotations

from esg_rag.schemas import SearchHit
from esg_rag.store import QdrantStore
from esg_rag.store import get_store

_store: QdrantStore | None = None


def _get_store() -> QdrantStore:
    global _store
    if _store is None:
        _store = QdrantStore()
    return _store

def bm25_search(query, k=30, filters=None, doc_ids=None):
    store = get_store()
    hits = store.search_sparse(query, top_k=k, doc_ids=doc_ids, filters=filters)
    for i, h in enumerate(hits):
        h.rank = i + 1
        h.search_type = "bm25"
    return hits