"""
components/cost_panel.py
------------------------
Sidebar cost tracker: reads data/albert_costs.jsonl and shows today's usage.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import streamlit as st

COST_LOG = Path("data/albert_costs.jsonl")
BUDGET_TOKENS = 2_000_000  # adjust to your actual budget


def render_cost_panel() -> None:
    st.markdown("### Usage")

    if not COST_LOG.exists():
        st.caption("No usage yet.")
        return

    rows = [json.loads(l) for l in COST_LOG.read_text().splitlines() if l.strip()]
    today = time.strftime("%Y-%m-%d")
    today_rows = [r for r in rows if r.get("ts", "").startswith(today)]

    total_in  = sum(r.get("tokens_in", 0)  for r in rows)
    today_in  = sum(r.get("tokens_in", 0)  for r in today_rows)
    today_out = sum(r.get("tokens_out", 0) for r in today_rows)
    pct = min(total_in / BUDGET_TOKENS * 100, 100) if BUDGET_TOKENS else 0

    st.markdown(
        f'<div style="font-size:0.78rem;color:#94a3b8">'
        f'Today: <strong style="color:#e2e8f0">{today_in:,}</strong> in · '
        f'<strong style="color:#e2e8f0">{today_out:,}</strong> out'
        f'</div>'
        f'<div class="cost-bar">'
        f'<div class="cost-fill" style="width:{pct:.1f}%"></div>'
        f'</div>'
        f'<div style="font-size:0.72rem;color:#6b7280">'
        f'Total: {total_in:,} / {BUDGET_TOKENS:,} tokens ({pct:.1f}%)'
        f'</div>',
        unsafe_allow_html=True,
    )

    # By caller breakdown (today)
    by_caller: dict[str, int] = {}
    for r in today_rows:
        caller = r.get("caller", "unknown")
        by_caller[caller] = by_caller.get(caller, 0) + r.get("tokens_in", 0)

    if by_caller:
        top = sorted(by_caller.items(), key=lambda x: -x[1])[:4]
        for caller, tokens in top:
            st.markdown(
                f'<div style="font-size:0.72rem;color:#6b7280">'
                f'{caller}: {tokens:,}'
                f'</div>',
                unsafe_allow_html=True,
            )
