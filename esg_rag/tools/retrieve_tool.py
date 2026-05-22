"""
esg_rag/tools/retrieve_tool.py
------------------------------
Tool: retrieve
Schema: {query, filters?, k?}
Calls retrieve.retrieve() and returns formatted evidence for the agent.
"""

from __future__ import annotations

from esg_rag.tools import register
from esg_rag.retrieve import retrieve


def _retrieve(
    query: str,
    filters: dict | None = None,
    k: int = 8,
) -> dict:
    """
    Retrieve relevant chunks from the ESG report index.

    Returns a dict with:
      - hits: list of {company, year, page, section, text, score}
      - n_hits: number of results
      - query_class: detected question type
    """
    result = retrieve(query, filters=filters or {})

    hits_out = []
    for h in result.hits[:k]:
        hits_out.append({
            "company":    h.company,
            "year":       h.year,
            "page":       h.page,
            "section":    h.section,
            "text":       h.text,
            "score":      round(h.score, 4),
            "source_pdf": h.source_pdf,
            "doc_id":     h.doc_id,
        })

    return {
        "hits":        hits_out,
        "n_hits":      len(hits_out),
        "query_class": result.query_class.label if result.query_class else "unknown",
        "telemetry":   result.telemetry,
    }


register(
    name="retrieve",
    description=(
        "Search the ESG report index for relevant evidence. "
        "Use this to find facts, metrics, targets, and disclosures from company sustainability reports. "
        "Pass filters like {\"company\": \"Apple\", \"year\": \"2024\"} to scope the search. "
        "Always call this before answering factual questions about company ESG data."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language search query, e.g. 'Apple Scope 1 GHG emissions 2022'",
            },
            "filters": {
                "type": "object",
                "description": "Optional filters: {company, year, report_type}",
                "properties": {
                    "company":     {"type": "string"},
                    "year":        {"type": "string"},
                    "report_type": {"type": "string"},
                },
            },
            "k": {
                "type": "integer",
                "description": "Number of results to return (default 8)",
                "default": 8,
            },
        },
        "required": ["query"],
    },
    fn=_retrieve,
)
