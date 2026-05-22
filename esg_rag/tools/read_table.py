"""
esg_rag/tools/read_table.py
----------------------------
Tool: read_table
Schema: {doc_id, table_id}
Loads a specific table chunk from the index and returns structured data.

table_id is the chunk_index of a chunk where has_table=True.
The agent discovers table_ids from retrieve() results where has_table=True.
"""

from __future__ import annotations

import json
import re

from esg_rag.tools import register
from esg_rag.store import get_store


def _read_table(doc_id: str, table_id: int) -> dict:
    """
    Retrieve a specific table from an indexed document.

    Returns:
      headers, rows, caption, units_hint, markdown
    """
    store = get_store()
    col = store._col(doc_id)

    try:
        points, _ = store._client.scroll(
            collection_name=col,
            limit=1000,
            with_payload=True,
        )
    except Exception as e:
        return {"error": f"Could not read collection {col}: {e}"}

    # Find the specific chunk
    target = None
    for p in points:
        payload = p.payload or {}
        if payload.get("chunk_index") == table_id and payload.get("has_table"):
            target = payload
            break

    if target is None:
        # Try to find any table chunk close to the requested id
        tables = [
            p.payload for p in points
            if (p.payload or {}).get("has_table")
        ]
        if not tables:
            return {"error": f"No table found with table_id={table_id} in doc {doc_id}"}
        # Return nearest by chunk_index
        target = min(tables, key=lambda t: abs(t.get("chunk_index", 0) - table_id))

    # Parse table_data
    raw_td = target.get("table_data", "[]")
    try:
        table_data = json.loads(raw_td) if isinstance(raw_td, str) else raw_td
    except Exception:
        table_data = []

    headers = []
    rows = []
    if table_data:
        headers = table_data[0].get("headers", [])
        rows    = table_data[0].get("rows", [])

    # Heuristic: detect units from headers or text
    text = target.get("text", "")
    units_hint = _detect_units(text + " ".join(str(h) for h in headers))

    return {
        "doc_id":     doc_id,
        "table_id":   table_id,
        "company":    target.get("company", ""),
        "year":       target.get("year", ""),
        "page":       target.get("page", 0),
        "section":    target.get("section", ""),
        "caption":    target.get("figure_caption", ""),
        "headers":    headers,
        "rows":       rows[:50],   # cap at 50 rows
        "units_hint": units_hint,
        "markdown":   text[:2000],
    }


def _detect_units(text: str) -> str:
    """Guess the primary unit from table text."""
    unit_patterns = [
        (r'\btCO2e?\b',        "tCO2e"),
        (r'\bMt\s*CO2',        "MtCO2e"),
        (r'\bGWh\b',           "GWh"),
        (r'\bMWh\b',           "MWh"),
        (r'\bm³\b',            "m³"),
        (r'\b(USD|EUR|€|\$)\b',"currency"),
        (r'\b%\b',             "%"),
        (r'\bFTE\b',           "FTE"),
    ]
    for pattern, unit in unit_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return unit
    return "unknown"


register(
    name="read_table",
    description=(
        "Read a specific table from an indexed ESG report. "
        "Use this when retrieve() returns a chunk with has_table=True and you need "
        "the structured rows and headers. "
        "Pass the doc_id and chunk_index (table_id) from the retrieve result."
    ),
    parameters={
        "type": "object",
        "properties": {
            "doc_id": {
                "type": "string",
                "description": "Document ID (12-char hash) from retrieve results",
            },
            "table_id": {
                "type": "integer",
                "description": "Chunk index of the table chunk (chunk_index from retrieve)",
            },
        },
        "required": ["doc_id", "table_id"],
    },
    fn=_read_table,
)
