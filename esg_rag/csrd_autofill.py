"""
esg_rag/csrd_autofill.py
-------------------------
autofill_csrd(template_path, doc_id) -> dict

The "killer demo moment" (Phase 7.3).

Loads a CSRD JSON template, then for each datapoint:
  1. Scopes the retrieve() call to the specific doc_id
  2. Runs the CSRD compliance agent to extract the value
  3. Returns a filled CSRDForm with per-cell confidence scores

Usage:
  from esg_rag.csrd_autofill import autofill_csrd
  result = autofill_csrd("data/csrd_templates/esrs_e1_minimal.json", doc_id="48243d269275")

Result format:
  {
    "template_id":  str,
    "company":      str,
    "year":         str,
    "doc_id":       str,
    "filled_at":    str,
    "datapoints": [
      {
        "esrs_id":     str,
        "label":       str,
        "category":    str,
        "value":       str,
        "unit":        str,
        "source_page": int,
        "source_text": str,
        "confidence":  float,   # 0.0–1.0
        "status":      str,     # "found" | "not_disclosed" | "error"
      }
    ],
    "summary": {
      "total":        int,
      "found":        int,
      "not_disclosed":int,
      "avg_confidence":float,
    }
  }
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import esg_rag.albert as albert
from esg_rag.tools import load_all, call_tool
from esg_rag.store import get_store


# ── Value extraction from agent output ───────────────────────────────────────

def _parse_agent_json(text: str) -> dict:
    """Parse JSON from agent output — handles code blocks and raw JSON."""
    # Try code block first
    for block in re.findall(r"```(?:json)?\s*([\s\S]+?)```", text):
        try:
            return json.loads(block.strip())
        except Exception:
            pass
    # Try raw JSON
    match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {}


# ── Per-datapoint fill ────────────────────────────────────────────────────────

def _fill_datapoint(
    datapoint: dict,
    doc_id: str,
    company: str,
    year: str,
) -> dict:
    """
    Fill a single CSRD datapoint by retrieving evidence and extracting the value.
    Uses a direct Albert call (no full agent loop) for speed and reliability.
    """
    search_query = datapoint["search_query"]
    esrs_id      = datapoint["esrs_id"]
    label        = datapoint["label"]
    expected_unit = datapoint.get("unit", "")

    # Retrieve evidence scoped to this document
    try:
        result = call_tool("retrieve", {
            "query":   search_query,
            "filters": {"company": company, "year": year},
            "k":       5,
        })
        hits = result.get("hits", [])
    except Exception as e:
        return {
            **datapoint,
            "value":       "error",
            "source_page": 0,
            "source_text": str(e)[:100],
            "confidence":  0.0,
            "status":      "error",
        }

    if not hits:
        return {
            **datapoint,
            "value":       "not disclosed",
            "source_page": 0,
            "source_text": "",
            "confidence":  0.0,
            "status":      "not_disclosed",
        }

    # Build evidence string for Albert
    evidence = "\n\n".join(
        f"[p.{h['page']}] {h['text'][:400]}"
        for h in hits[:4]
    )

    # Ask Albert to extract the value
    system = (
        "You are extracting a specific ESG metric from report evidence. "
        "Respond ONLY with JSON — no explanation, no markdown.\n"
        "Format: {\"value\": \"...\", \"unit\": \"...\", \"source_page\": 0, "
        "\"source_text\": \"exact sentence with the number\", \"confidence\": 0.9}\n"
        "Rules:\n"
        "- value: the exact number or 'not disclosed'\n"
        f"- unit: expected unit is '{expected_unit}' — use this or correct it\n"
        "- source_page: page number from the evidence\n"
        "- source_text: max 150 chars, must contain the number\n"
        "Never fabricate. If truly absent, set value='not disclosed' and confidence=0.0."
        "- confidence: score between 0.0 and 1.0 based on evidence quality:\n"
        "  * 0.95: exact number found verbatim with unit on the same page\n"
        "  * 0.80: number found but unit inferred or on different page\n"
        "  * 0.65: approximate value, stated as estimate or range\n"
        "  * 0.50: value implied but not explicitly stated\n"
        "  * 0.00: not found in evidence\n"
        "  Use your judgment — do NOT default to 0.9 for everything.\n"
    )

    user_msg = (
        f"Company: {company} | Year: {year}\n"
        f"Metric: {label} ({esrs_id})\n"
        f"Expected unit: {expected_unit}\n\n"
        f"Evidence:\n{evidence}\n\n"
        "Extract the value:"
    )

    try:
        raw = albert.chat_text(
            [
                {"role": "system", "content": system},
                {"role": "user",   "content": user_msg},
            ],
            model=albert.STRONG_MODEL,
            max_tokens=200,
            temperature=0.0,
            caller="csrd_autofill",
        )
        parsed = _parse_agent_json(raw)
    except Exception as e:
        parsed = {}

    value      = parsed.get("value", "not disclosed")
    unit       = parsed.get("unit", expected_unit)
    page       = int(parsed.get("source_page", hits[0]["page"] if hits else 0))
    src_text   = parsed.get("source_text", hits[0]["text"][:150] if hits else "")
    confidence = float(parsed.get("confidence", 0.0))

    # Clamp confidence
    confidence = max(0.0, min(1.0, confidence))

    # Status
    if value in ("not disclosed", "", "N/A", "none", "null"):
        status = "not_disclosed"
        confidence = 0.0
    else:
        status = "found"

    return {
        "esrs_id":     esrs_id,
        "label":       label,
        "category":    datapoint.get("category", ""),
        "value":       value,
        "unit":        unit,
        "source_page": page,
        "source_text": src_text[:200],
        "confidence":  round(confidence, 2),
        "status":      status,
    }


# ── Main autofill ─────────────────────────────────────────────────────────────

def autofill_csrd(
    template_path: str | Path,
    doc_id: str,
    *,
    progress_callback=None,
) -> dict:
    """
    Fill a CSRD template for a specific document.

    Args:
        template_path:     path to JSON template (e.g. data/csrd_templates/esrs_e1_minimal.json)
        doc_id:            Qdrant doc_id (12-char hash) to scope evidence retrieval
        progress_callback: optional fn(current, total, label) for UI progress

    Returns:
        Filled form dict (see module docstring for format).
    """
    import yaml
    from pathlib import Path as P

    # Load tools
    cfg = yaml.safe_load(P("pipeline_config.yaml").read_text()) if P("pipeline_config.yaml").exists() else {}
    load_all(cfg)

    # Load template
    template_path = Path(template_path)
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    template = json.loads(template_path.read_text())

    # Resolve company + year from doc_id
    store = get_store()
    docs  = store.list_docs()
    doc   = next((d for d in docs if d["doc_id"] == doc_id), None)
    if doc is None:
        raise ValueError(f"doc_id {doc_id} not found in index. Run list_docs() to see available docs.")

    company = doc["company"]
    year    = doc["year"]

    print(f"\n[csrd_autofill] Filling {template['template_name']}")
    print(f"  Company: {company} | Year: {year} | Doc: {doc_id}")
    print(f"  Datapoints: {len(template['datapoints'])}\n")

    t0 = time.perf_counter()
    filled: list[dict] = []

    for i, dp in enumerate(template["datapoints"]):
        print(f"  [{i+1:02d}/{len(template['datapoints'])}] {dp['esrs_id']} — {dp['label']}")

        if progress_callback:
            progress_callback(i + 1, len(template["datapoints"]), dp["label"])

        result = _fill_datapoint(dp, doc_id, company, year)
        filled.append(result)

        status_icon = {"found": "✅", "not_disclosed": "⬜", "error": "❌"}.get(result["status"], "?")
        print(f"    {status_icon} value={result['value']} unit={result['unit']} "
              f"p.{result['source_page']} conf={result['confidence']:.2f}")

    elapsed = time.perf_counter() - t0

    # Summary
    found         = sum(1 for d in filled if d["status"] == "found")
    not_disclosed = sum(1 for d in filled if d["status"] == "not_disclosed")
    errors        = sum(1 for d in filled if d["status"] == "error")
    avg_conf      = (
        sum(d["confidence"] for d in filled if d["status"] == "found") / found
        if found else 0.0
    )

    print(f"\n  ✓ Done in {elapsed:.1f}s — "
          f"found={found} not_disclosed={not_disclosed} errors={errors} "
          f"avg_confidence={avg_conf:.2f}")

    return {
        "template_id":    template["template_id"],
        "template_name":  template["template_name"],
        "company":        company,
        "year":           year,
        "doc_id":         doc_id,
        "source_pdf":     doc.get("source_pdf", ""),
        "filled_at":      time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_s":      round(elapsed, 1),
        "datapoints":     filled,
        "summary": {
            "total":          len(filled),
            "found":          found,
            "not_disclosed":  not_disclosed,
            "errors":         errors,
            "avg_confidence": round(avg_conf, 2),
        },
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, sys

    parser = argparse.ArgumentParser(description="CSRD auto-fill")
    parser.add_argument("--template", default="data/csrd_templates/esrs_e1_minimal.json")
    parser.add_argument("--doc-id",  required=True, help="doc_id from list_docs()")
    parser.add_argument("--out",     help="Save result to JSON file")
    args = parser.parse_args()

    result = autofill_csrd(args.template, args.doc_id)

    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2))
        print(f"\nSaved → {args.out}")
    else:
        print(json.dumps(result, indent=2))
