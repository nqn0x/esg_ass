"""
esg_rag/tools/compare_documents.py
------------------------------------
Tool: compare_documents
Schema: {metric_query, doc_ids?, companies?, year?}

For each company/doc: scoped retrieve → extract value via regex → return
a structured comparison table ready for the UI.

Return format:
  {
    "headers": ["company", "year", "value", "unit", "source_page", "source_text"],
    "rows": [...],
    "metric_query": "...",
  }

This is the tool that powers the cross-document compare view in the UI.
"""

from __future__ import annotations

import re

from esg_rag.tools import register
from esg_rag.retrieve import retrieve
from esg_rag.store import get_store


# ── Value extraction helpers ──────────────────────────────────────────────────

_NUMBER_RE = re.compile(
    r'(?:^|[\s:=\(])([+-]?\d[\d,]*(?:\.\d+)?)\s*'
    r'(tCO2e?|MtCO2e?|GtCO2e?|GWh|MWh|kWh|TWh|m³|Mm³|%|USD|EUR|€|\$|Mt|kt|MW|GW|FTE)?',
    re.IGNORECASE,
)


def _extract_value(text: str) -> tuple[str, str]:
    """
    Extract the most prominent number + unit from a text chunk.
    Returns (value_str, unit_str).
    """
    matches = _NUMBER_RE.findall(text)
    if not matches:
        return "not found", ""

    # Prefer matches with explicit units
    for val, unit in matches:
        if unit:
            val_clean = val.replace(",", "")
            return val_clean, unit

    # Fall back to first number
    val = matches[0][0].replace(",", "")
    return val, ""


# ── Core function ─────────────────────────────────────────────────────────────

def _compare_documents(
    metric_query: str,
    doc_ids: list[str] | None = None,
    companies: list[str] | None = None,
    year: str | None = None,
) -> dict:
    """
    Compare a specific metric across multiple companies.

    Args:
        metric_query: what to look for, e.g. "Scope 1 GHG emissions"
        doc_ids:      specific doc IDs to compare (optional)
        companies:    company names to compare (optional, used if no doc_ids)
        year:         filter by year (optional)

    Returns structured comparison table.
    """
    store = get_store()
    all_docs = store.list_docs()

    # Resolve which docs to compare
    if doc_ids:
        target_docs = [d for d in all_docs if d["doc_id"] in doc_ids]
    elif companies:
        target_docs = [
            d for d in all_docs
            if any(c.lower() in d["company"].lower() for c in companies)
            and (not year or d["year"] == str(year))
        ]
    else:
        # Default: all docs for the given year, or all docs
        target_docs = [
            d for d in all_docs
            if not year or d["year"] == str(year)
        ]

    if not target_docs:
        return {
            "error": "No matching documents found",
            "metric_query": metric_query,
            "headers": [],
            "rows": [],
        }

    rows = []
    for doc in target_docs:
        # Scoped retrieve for this document
        result = retrieve(
            metric_query,
            filters={"company": doc["company"], "year": doc["year"]},
        )

        if not result.hits:
            rows.append({
                "company":     doc["company"],
                "year":        doc["year"],
                "value":       "not disclosed",
                "unit":        "",
                "source_page": 0,
                "source_text": "",
            })
            continue

        # Use top hit
        top = result.hits[0]
        value, unit = _extract_value(top.text)

        rows.append({
            "company":     doc["company"],
            "year":        doc["year"],
            "value":       value,
            "unit":        unit,
            "source_page": top.page,
            "source_text": top.text[:200],
            "doc_id":      doc["doc_id"],
            "section":     top.section,
        })

    # Sort by company name
    rows.sort(key=lambda r: (r["company"], r["year"]))

    return {
        "metric_query": metric_query,
        "headers": ["company", "year", "value", "unit", "source_page"],
        "rows": rows,
        "n_companies": len(rows),
    }


register(
    name="compare_documents",
    description=(
        "Compare a specific ESG metric across multiple companies or years. "
        "Returns a structured table with values, units, and source pages. "
        "Use this for cross-company comparisons like 'Compare Scope 1 emissions across tech companies'. "
        "Specify companies list to restrict comparison, or leave empty to compare all indexed companies."
    ),
    parameters={
        "type": "object",
        "properties": {
            "metric_query": {
                "type": "string",
                "description": "The metric to compare, e.g. 'Scope 1 GHG emissions', 'water consumption', 'renewable energy percentage'",
            },
            "doc_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of specific doc IDs to compare",
            },
            "companies": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of company names to compare, e.g. ['Apple', 'Microsoft', 'Google']",
            },
            "year": {
                "type": "string",
                "description": "Optional year filter, e.g. '2023'",
            },
        },
        "required": ["metric_query"],
    },
    fn=_compare_documents,
)
