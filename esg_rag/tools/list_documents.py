"""
esg_rag/tools/list_documents.py
--------------------------------
Tool: list_documents
Schema: {}
Returns all indexed documents so the agent knows what's available.
"""

from __future__ import annotations

from esg_rag.tools import register
from esg_rag.store import get_store


def _list_documents() -> dict:
    """
    List all ESG reports currently indexed and available for search.
    Returns company names, years, report types, and chunk counts.
    """
    store = get_store()
    docs = store.list_docs()

    # Group by company for cleaner output
    by_company: dict[str, list] = {}
    for d in docs:
        company = d["company"]
        by_company.setdefault(company, []).append({
            "year":        d["year"],
            "report_type": d["report_type"],
            "n_chunks":    d["n_chunks"],
            "doc_id":      d["doc_id"],
            "source_pdf":  d["source_pdf"],
        })

    return {
        "total_docs": len(docs),
        "total_chunks": sum(d["n_chunks"] for d in docs),
        "companies": sorted(by_company.keys()),
        "years_available": sorted(set(d["year"] for d in docs)),
        "summary": f"{len(docs)} reports indexed: {', '.join(sorted(by_company.keys())[:10])}{'...' if len(by_company) > 10 else ''}",
    }


register(
    name="list_documents",
    description=(
        "List all ESG reports available in the index. "
        "Call this first when the user asks about a company you're not sure is indexed, "
        "or to discover what years and companies are available."
    ),
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
    fn=_list_documents,
)
