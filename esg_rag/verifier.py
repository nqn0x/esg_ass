"""
esg_rag/verifier.py
--------------------
verify_claims(answer, contexts) -> {claims, unsupported_count}

Fast (<100ms) regex-based pre-check that runs before the fact_checker agent.
Checks whether numeric claims in the answer appear in the retrieved contexts.
Complements the fact_checker agent (which is slower but more thorough).

Used by answer_question() to add a verifier_result to the response.
"""

from __future__ import annotations

import re
from typing import Any


_NUMBER_RE = re.compile(r'\b\d[\d,.\-]*\s*(?:tCO2e?|MtCO2e?|GWh|MWh|%|billion|million|thousand|USD|EUR|\$|€)?\b')
_CITATION_RE = re.compile(r'\[([A-Za-z\s]+)\s+(\d{4})\s+p\.(\d+)\]')


def _extract_numbers(text: str) -> set[str]:
    """Extract all numeric tokens from text for comparison."""
    matches = _NUMBER_RE.findall(text)
    # Normalise: remove commas, lowercase
    return {m.replace(",", "").strip().lower() for m in matches if len(m.strip()) > 1}


def _extract_claims(answer: str) -> list[str]:
    """
    Split answer into sentences containing numeric claims.
    Returns sentences that contain numbers (these need verification).
    """
    sentences = re.split(r'(?<=[.!?])\s+', answer)
    return [s for s in sentences if _NUMBER_RE.search(s) and len(s.strip()) > 20]


def verify_claims(
    answer: str,
    contexts: list[str],
) -> dict[str, Any]:
    """
    Check whether numeric claims in the answer are supported by contexts.

    Args:
        answer:   generated answer text
        contexts: list of retrieved chunk texts

    Returns:
        {
            "claims": [{"text": str, "supported": bool, "source": str}],
            "unsupported_count": int,
            "verdict": "pass" | "warn" | "fail"
        }
    """
    if not answer or not contexts:
        return {"claims": [], "unsupported_count": 0, "verdict": "pass"}

    # Build searchable corpus from all contexts
    corpus = " ".join(contexts).lower()
    corpus_numbers = _extract_numbers(corpus)

    claims_out = []
    claim_sentences = _extract_claims(answer)

    for sent in claim_sentences:
        claim_numbers = _extract_numbers(sent)
        if not claim_numbers:
            continue

        # Check if any number from this claim appears in the corpus
        overlap = claim_numbers & corpus_numbers
        supported = len(overlap) > 0

        # Find which context supports it
        source = ""
        if supported:
            for i, ctx in enumerate(contexts):
                ctx_nums = _extract_numbers(ctx)
                if claim_numbers & ctx_nums:
                    source = f"context_{i+1}"
                    break

        claims_out.append({
            "text":      sent[:200],
            "supported": supported,
            "source":    source,
            "numbers_checked": list(claim_numbers)[:5],
        })

    unsupported = sum(1 for c in claims_out if not c["supported"])

    if unsupported == 0:
        verdict = "pass"
    elif unsupported <= 1:
        verdict = "warn"
    else:
        verdict = "fail"

    return {
        "claims":            claims_out,
        "unsupported_count": unsupported,
        "verdict":           verdict,
        "n_claims_checked":  len(claims_out),
    }
