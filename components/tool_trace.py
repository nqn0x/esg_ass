"""
components/tool_trace.py
-------------------------
Renders tool_trace list as a collapsible nested trace.
Each tool call shows: name, args summary, latency, result preview.
MCP tools get a distinct badge (for Phase 7).
"""

from __future__ import annotations

import json
import streamlit as st


_TOOL_COLORS = {
    "retrieve":          "#1e3a5f",
    "compute":           "#2d1b69",
    "compare_documents": "#1a3a1a",
    "list_documents":    "#1a2e1a",
    "read_table":        "#3a2a1a",
    "fetch_regulation":  "#1a2a3a",
    "web_search":        "#3a1a1a",
    "spawn_subagent":    "#2a1a3a",
}

_TOOL_ICONS = {
    "retrieve":          "🔍",
    "compute":           "🧮",
    "compare_documents": "⚖️",
    "list_documents":    "📚",
    "read_table":        "📋",
    "fetch_regulation":  "📜",
    "web_search":        "🌐",
    "spawn_subagent":    "🤖",
}


def _args_summary(tool: str, args: dict) -> str:
    """One-line summary of tool arguments."""
    if tool == "retrieve":
        q = args.get("query", "")[:50]
        f = args.get("filters", {})
        fstr = f" [{', '.join(f'{k}={v}' for k,v in f.items())}]" if f else ""
        return f'"{q}"{fstr}'
    if tool == "compute":
        return args.get("expression", "")[:60]
    if tool == "compare_documents":
        return args.get("metric_query", "")[:50]
    if tool == "spawn_subagent":
        return f"{args.get('agent_type','')} → {args.get('task','')[:40]}"
    if tool == "fetch_regulation":
        return args.get("regulation_id", "")
    return str(args)[:60]


def _result_preview(tool: str, result: dict | list | str) -> str:
    """Short preview of tool result."""
    if isinstance(result, dict):
        if "error" in result:
            return f"❌ {result['error'][:80]}"
        if tool == "retrieve":
            n = result.get("n_hits", 0)
            top = result.get("hits", [{}])[0].get("text", "")[:80] if result.get("hits") else ""
            return f"{n} hits · {top}…"
        if tool == "compute":
            return f"= {result.get('formatted', result.get('result', ''))}"
        if tool == "compare_documents":
            n = result.get("n_companies", 0)
            return f"{n} companies compared"
        if tool == "spawn_subagent":
            out = result.get("final_output", "")[:100]
            iters = result.get("iterations_used", 0)
            return f"{iters} iters · {out}…"
        return str(result)[:100]
    return str(result)[:100]


def render_tool_trace(tool_trace: list[dict], indent: int = 0) -> None:
    """Render tool trace with color coding and nested subagent traces."""
    for i, entry in enumerate(tool_trace):
        tool    = entry.get("tool", "unknown")
        args    = entry.get("args", {})
        result  = entry.get("result", {})
        latency = entry.get("latency_ms", 0)
        icon    = _TOOL_ICONS.get(tool, "🔧")
        summary = _args_summary(tool, args)
        preview = _result_preview(tool, result)

        st.markdown(
            f'<div style="margin-left:{indent*16}px;margin-bottom:6px">'
            f'<span class="tool-chip tool-chip-{tool}">{icon} {tool}</span> '
            f'<span style="font-family:DM Mono,monospace;font-size:0.72rem;color:#94a3b8">'
            f'{summary}</span> '
            f'<span style="font-size:0.7rem;color:#6b7280">{latency:.0f}ms</span>'
            f'<br><span style="font-size:0.75rem;color:#9ca3af;margin-left:{indent*16+12}px">'
            f'↳ {preview}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Render nested subagent traces
        if tool == "spawn_subagent" and isinstance(result, dict):
            sub_trace = result.get("tool_trace_summary", [])
            if sub_trace:
                for sub in sub_trace:
                    sub_tool = sub.get("tool", "")
                    sub_lat  = sub.get("latency_ms", 0)
                    sub_icon = _TOOL_ICONS.get(sub_tool, "🔧")
                    st.markdown(
                        f'<div style="margin-left:{(indent+1)*16}px;margin-bottom:3px">'
                        f'<span class="tool-chip" style="font-size:0.65rem">'
                        f'{sub_icon} {sub_tool}</span> '
                        f'<span style="font-size:0.68rem;color:#6b7280">{sub_lat:.0f}ms</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
