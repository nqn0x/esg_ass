"""
components/chat.py
------------------
Main chat interface:
  - Message history display with citation formatting
  - Input box → answer_question()
  - Tool trace expander
  - Verifier badge
  - Streaming "thinking…" indicator
"""

from __future__ import annotations

import re
import time

import streamlit as st

from components.citations import format_citations, render_citation_sidebar
from components.tool_trace import render_tool_trace


def _format_answer(text: str) -> str:
    """Format answer text: highlight [Company Year p.X] citations as badges."""
    pattern = r'\[([^\]]+p\.\d+[^\]]*)\]'
    def replace(m):
        cite = m.group(1)
        return f'<span class="citation-badge" title="{cite}">📄 {cite}</span>'
    return re.sub(pattern, replace, text)


def _render_message(msg: dict, idx: int) -> None:
    """Render a single chat message."""
    role = msg["role"]
    content = msg["content"]
    meta = msg.get("metadata", {})

    if role == "user":
        st.markdown(
            f'<div class="user-bubble">{content}</div>',
            unsafe_allow_html=True,
        )
        return

    # Assistant message
    formatted = _format_answer(content)
    st.markdown(
        f'<div class="assistant-bubble">{formatted}</div>',
        unsafe_allow_html=True,
    )

    # Metadata row
    if meta:
        col1, col2, col3 = st.columns([2, 2, 2])

        # Verifier badge
        verdict = meta.get("verifier_result", {}).get("verdict", "")
        if verdict:
            icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}.get(verdict, "")
            cls  = f"verdict-{verdict}"
            with col1:
                st.markdown(
                    f'<span class="{cls}">{icon} {verdict.upper()}</span>',
                    unsafe_allow_html=True,
                )

        # Latency
        latency = meta.get("telemetry", {}).get("latency_ms", 0)
        if latency:
            with col2:
                st.markdown(
                    f'<span style="font-size:0.75rem;color:#9ca3af">⏱ {latency:.0f}ms</span>',
                    unsafe_allow_html=True,
                )

        # Tool trace expander
        tool_trace = meta.get("tool_trace", [])
        if tool_trace:
            with col3:
                with st.expander(f"🔧 {len(tool_trace)} tool calls"):
                    render_tool_trace(tool_trace)


def render_chat() -> None:
    """Render the full chat interface."""

    # Message history
    for i, msg in enumerate(st.session_state.messages):
        _render_message(msg, i)

    # Clear button
    if st.session_state.messages:
        if st.button("🗑 Clear chat", key="clear_chat"):
            st.session_state.messages = []
            st.session_state.last_result = None
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Example questions
    if not st.session_state.messages:
        st.markdown("**Try asking:**")
        examples = [
            "What are Apple's Scope 1 emissions in 2022?",
            "Compare Microsoft and Google's water usage in 2023",
            "What is Nike's net zero target?",
            "What does ESRS E1 require for Scope 3 reporting?",
            "How did Tesla's emissions change year over year?",
        ]
        cols = st.columns(len(examples))
        for col, ex in zip(cols, examples):
            with col:
                if st.button(ex, key=f"ex_{ex[:20]}", use_container_width=True):
                    st.session_state._pending_question = ex
                    st.rerun()

    # Handle example button click
    if hasattr(st.session_state, "_pending_question"):
        question = st.session_state._pending_question
        del st.session_state._pending_question
        _run_question(question)
        st.rerun()

    # Input
    with st.form("chat_form", clear_on_submit=True):
        col_input, col_btn = st.columns([5, 1])
        with col_input:
            question = st.text_input(
                "question",
                placeholder="Ask anything about ESG reports…",
                label_visibility="collapsed",
            )
        with col_btn:
            submitted = st.form_submit_button("Ask →", use_container_width=True)

    if submitted and question.strip():
        _run_question(question.strip())
        st.rerun()

    # Citation side panel
    if st.session_state.last_result:
        render_citation_sidebar(st.session_state.last_result)


def _run_question(question: str) -> None:
    """Process a question and add result to message history."""
    from esg_rag.synthesize import answer_question

    # Add user message
    st.session_state.messages.append({"role": "user", "content": question})

    # Show thinking indicator
    with st.spinner("Searching reports…"):
        t0 = time.perf_counter()
        result = answer_question(
            question,
            filters=st.session_state.doc_filters,
            config=st.session_state.config,
        )
        elapsed = (time.perf_counter() - t0) * 1000

    result["telemetry"]["latency_ms"] = elapsed
    st.session_state.last_result = result

    # Add assistant message with metadata
    st.session_state.messages.append({
        "role":    "assistant",
        "content": result["answer"],
        "metadata": {
            "verifier_result": result.get("verifier_result", {}),
            "tool_trace":      result.get("tool_trace", []),
            "telemetry":       result.get("telemetry", {}),
            "hits":            result.get("hits", []),
        },
    })
