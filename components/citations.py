"""
components/citations.py
-----------------------
Citation cards and source panel.
Parses [Company Year p.X] markers from answers and renders clickable source cards.
"""

from __future__ import annotations

import re
import streamlit as st


def format_citations(text: str) -> str:
    """Replace [Company Year p.X] with styled badge HTML."""
    pattern = r'\[([A-Za-z &]+)\s+(\d{4})\s+p\.(\d+)\]'
    def replace(m):
        company, year, page = m.group(1), m.group(2), m.group(3)
        return (
            f'<span class="citation-badge" '
            f'title="{company} {year} · page {page}">'
            f'📄 {company} {year} p.{page}</span>'
        )
    return re.sub(pattern, replace, text)


def render_citation_sidebar(result: dict) -> None:
    """Show source chunks as expandable cards below the chat."""
    hits = result.get("hits", [])
    if not hits:
        return

    st.markdown("---")
    st.markdown("**📄 Source Evidence**")

    for i, h in enumerate(hits[:6], 1):
        if isinstance(h, dict):
            company = h.get("company", "")
            year    = h.get("year", "")
            page    = h.get("page", "")
            section = h.get("section", "")
            text    = h.get("text", "")
            score   = h.get("score", 0)
        else:
            company = getattr(h, "company", "")
            year    = getattr(h, "year", "")
            page    = getattr(h, "page", "")
            section = getattr(h, "section", "")
            text    = getattr(h, "text", "")
            score   = getattr(h, "score", 0)

        score_pct = int(float(score) * 100) if score else 0
        header    = f"[{i}] {company} {year} · p.{page}"
        if section:
            header += f" · {section[:40]}"

        with st.expander(header, expanded=(i == 1)):
            st.markdown(
                f'<div style="font-size:0.82rem;line-height:1.6;color:#374151">'
                f'{text[:600]}{"…" if len(text) > 600 else ""}'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<span style="font-size:0.72rem;color:#9ca3af">'
                f'Relevance: {score_pct}%</span>',
                unsafe_allow_html=True,
            )
