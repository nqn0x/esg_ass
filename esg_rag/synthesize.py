"""
esg_rag/synthesize.py
---------------------
synthesize_answer(question, hits) -> str
answer_question(question, filters, config)  -> dict

answer_question is the main entry point used by:
  - eval harness (Phase 4)
  - Streamlit UI (Phase 8)
  - CLI testing

Routes based on config.agent.mode:
  "simple"       → retrieve + synthesize (fast, single Albert call)
  "orchestrated" → lead_orchestrator multi-agent pipeline
"""

from __future__ import annotations

import time
from typing import Any, Generator
from pathlib import Path

import esg_rag.albert as albert
from esg_rag.schemas import SearchHit
from esg_rag.verifier import verify_claims

SYSTEM = """You are a precise ESG analyst assistant.
Answer the question using ONLY the provided evidence excerpts.
Cite sources as [Company Year p.PAGE] after each claim.
If the evidence does not contain enough information, say so clearly.
Do NOT fabricate numbers or facts not present in the evidence.
Be concise — 3-5 sentences maximum unless the question requires more."""


# ── Simple synthesis ──────────────────────────────────────────────────────────

def synthesize_answer(
    question: str,
    hits: list[SearchHit] | list[dict],
    model: str = albert.STRONG_MODEL,
) -> str:
    """Generate a grounded answer from retrieved chunks."""
    if not hits:
        return "No relevant information found in the indexed reports."

    evidence_lines = []
    for i, h in enumerate(hits[:8], 1):
        if isinstance(h, dict):
            text    = h.get("text", "")
            company = h.get("company", "")
            year    = h.get("year", "")
            page    = h.get("page", "")
            section = h.get("section", "")
        else:
            text    = h.text
            company = h.company
            year    = h.year
            page    = h.page
            section = h.section
        evidence_lines.append(f"[{i}] {company} {year} p.{page} | {section}\n{text}")

    evidence = "\n\n".join(evidence_lines)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user",   "content": f"Question: {question}\n\nEvidence:\n{evidence}"},
    ]

    try:
        return albert.chat_text(
            messages,
            model=model,
            max_tokens=512,
            temperature=0.0,
            caller="synthesize",
        )
    except Exception as e:
        return f"[synthesis error: {e}]"


def synthesize_stream(
    question: str,
    hits: list,
    model: str = albert.STRONG_MODEL,
) -> Generator[str, None, None]:
    """Streaming version — yields tokens as they arrive."""
    if not hits:
        yield "No relevant information found in the indexed reports."
        return

    evidence_lines = []
    for i, h in enumerate(hits[:8], 1):
        if isinstance(h, dict):
            text, company, year, page, section = (
                h.get("text",""), h.get("company",""), h.get("year",""),
                h.get("page",""), h.get("section",""),
            )
        else:
            text, company, year, page, section = h.text, h.company, h.year, h.page, h.section
        evidence_lines.append(f"[{i}] {company} {year} p.{page} | {section}\n{text}")

    evidence = "\n\n".join(evidence_lines)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user",   "content": f"Question: {question}\n\nEvidence:\n{evidence}"},
    ]

    try:
        yield from albert.chat_stream(messages, model=model, caller="synthesize_stream")
    except Exception as e:
        yield f"[synthesis error: {e}]"


# ── Main entry point ──────────────────────────────────────────────────────────

def answer_question(
    question: str,
    filters: dict | None = None,
    config: dict | None = None,
    stream: bool = False,
) -> dict[str, Any]:
    """
    Full pipeline: retrieve → synthesize (simple) or orchestrate (multi-agent).

    Returns:
        {
            answer:             str,
            retrieved_contexts: list[str],
            hits:               list,
            telemetry:          dict,
            verifier_result:    dict,
            tool_trace:         list,
            mode:               "simple" | "orchestrated",
        }
    """
    from esg_rag.retrieve import retrieve
    from esg_rag.tools import load_all

    t0 = time.perf_counter()
    if config is None:
        import yaml
        cfg_path = Path("pipeline_config.yaml")
        config = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
    filters = filters or {}
    mode    = config.get("agent", {}).get("mode", "simple")

    load_all(config)

    # ── Simple mode ───────────────────────────────────────────────────────────
    if mode == "simple":
        result = retrieve(question, filters=filters, config=config)
        answer = synthesize_answer(question, result.hits)
        ctx_texts = [h.text for h in result.hits]

        verifier = verify_claims(answer, ctx_texts)

        return {
            "answer":             answer,
            "retrieved_contexts": ctx_texts,
            "hits":               result.hits,
            "telemetry":          {
                **result.telemetry,
                "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
                "mode": "simple",
            },
            "verifier_result":    verifier,
            "tool_trace":         [],
            "mode":               "simple",
        }

    # ── Orchestrated mode ─────────────────────────────────────────────────────
    from esg_rag.agents import run_agent
    from esg_rag.agents.lead_orchestrator import LEAD_ORCHESTRATOR

    agent_result = run_agent(LEAD_ORCHESTRATOR, question)
    ctx_texts    = [
        h.get("text", "") if isinstance(h, dict) else h.text
        for h in agent_result.retrieved_contexts
    ]
    verifier     = verify_claims(agent_result.final_output, ctx_texts)

    return {
        "answer":             agent_result.final_output,
        "retrieved_contexts": ctx_texts,
        "hits":               agent_result.retrieved_contexts,
        "telemetry":          {
            "elapsed_ms":      round((time.perf_counter() - t0) * 1000, 1),
            "iterations_used": agent_result.iterations_used,
            "tokens":          agent_result.tokens,
            "mode":            "orchestrated",
        },
        "verifier_result":    verifier,
        "tool_trace":         agent_result.tool_trace,
        "mode":               "orchestrated",
    }
