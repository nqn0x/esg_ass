"""
components/csrd_view.py
------------------------
CSRD auto-fill UI tab (Phase 8.7).

Features:
  - Template dropdown (esrs_e1_minimal for now)
  - Company + year selector → resolves to doc_id
  - "Fill Form" button → autofill_csrd() with progress bar
  - Results table: value, unit, source link, confidence (green/yellow/red)
  - Export as CSV or JSON
"""

from __future__ import annotations

import json
import io
import time
from pathlib import Path

import streamlit as st


_TEMPLATES = {
    "ESRS E1 — Climate Change (Minimal)": "data/csrd_templates/esrs_e1_minimal.json",
}

_CONFIDENCE_COLORS = {
    "high":   "#16a34a",   # ≥0.8 → green
    "medium": "#d97706",   # 0.5–0.8 → amber
    "low":    "#6b7280",   # <0.5 → grey (not_disclosed)
    "error":  "#dc2626",   # error → red
}


def _confidence_badge(conf: float, status: str) -> str:
    if status == "error":
        color = _CONFIDENCE_COLORS["error"]
        label = "ERROR"
    elif status == "not_disclosed":
        color = _CONFIDENCE_COLORS["low"]
        label = "N/D"
    elif conf >= 0.8:
        color = _CONFIDENCE_COLORS["high"]
        label = f"{int(conf*100)}%"
    elif conf >= 0.5:
        color = _CONFIDENCE_COLORS["medium"]
        label = f"{int(conf*100)}%"
    else:
        color = _CONFIDENCE_COLORS["low"]
        label = f"{int(conf*100)}%"

    return (
        f'<span style="background:{color};color:white;border-radius:4px;'
        f'padding:2px 7px;font-size:0.75rem;font-weight:600">{label}</span>'
    )


@st.cache_data(ttl=60)
def _get_docs_for_csrd():
    from esg_rag.store import get_store
    docs = get_store().list_docs()
    # Build label → doc mapping
    options = {}
    for d in docs:
        label = f"{d['company']} — {d['year']}"
        options[label] = d
    return options


def render_csrd_view() -> None:
    st.markdown("### 📋 CSRD Auto-Fill — ESRS E1")
    st.markdown(
        "Select a company report and click **Fill Form** to automatically extract "
        "ESRS E1 Climate Change datapoints from the indexed sustainability report."
    )

    col1, col2 = st.columns([2, 2])

    with col1:
        template_name = st.selectbox(
            "Template",
            list(_TEMPLATES.keys()),
        )
        template_path = _TEMPLATES[template_name]

    with col2:
        doc_options = _get_docs_for_csrd()
        if not doc_options:
            st.error("No documents indexed. Run ingest first.")
            return
        selected_label = st.selectbox(
            "Company Report",
            list(doc_options.keys()),
        )
        selected_doc = doc_options[selected_label]

    # Info
    st.markdown(
        f'<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;'
        f'padding:10px 14px;font-size:0.82rem;color:#166534;margin:8px 0">'
        f'📄 <strong>{selected_doc["source_pdf"]}</strong> · '
        f'{selected_doc["n_chunks"]:,} chunks indexed · doc_id: '
        f'<code>{selected_doc["doc_id"]}</code>'
        f'</div>',
        unsafe_allow_html=True,
    )

    fill_clicked = st.button(
        "🤖 Fill Form Automatically",
        type="primary",
        use_container_width=True,
    )

    # ── Run autofill ──────────────────────────────────────────────────────────
    if fill_clicked:
        from esg_rag.csrd_autofill import autofill_csrd

        template = json.loads(Path(template_path).read_text())
        n_datapoints = len(template["datapoints"])

        progress_bar  = st.progress(0, text="Starting…")
        status_text   = st.empty()

        def on_progress(current, total, label):
            progress_bar.progress(current / total, text=f"Filling: {label}")
            status_text.markdown(
                f'<span style="font-size:0.8rem;color:#6b7280">'
                f'[{current}/{total}] {label}</span>',
                unsafe_allow_html=True,
            )

        t0 = time.perf_counter()
        try:
            result = autofill_csrd(
                template_path,
                selected_doc["doc_id"],
                progress_callback=on_progress,
            )
            progress_bar.progress(1.0, text="Complete!")
            status_text.empty()
            st.session_state["csrd_result"] = result
        except Exception as e:
            st.error(f"Autofill failed: {e}")
            progress_bar.empty()
            status_text.empty()
            return

    # ── Render results ────────────────────────────────────────────────────────
    result = st.session_state.get("csrd_result")
    if result is None:
        return

    # Check it matches current selection
    if result.get("doc_id") != selected_doc["doc_id"]:
        st.info("Click 'Fill Form' to generate results for this report.")
        return

    summary = result["summary"]
    st.markdown("---")

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value">{summary["found"]}/{summary["total"]}</div>'
            f'<div class="metric-label">Datapoints Found</div>'
            f'</div>', unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value">{int(summary["avg_confidence"]*100)}%</div>'
            f'<div class="metric-label">Avg Confidence</div>'
            f'</div>', unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value">{summary["not_disclosed"]}</div>'
            f'<div class="metric-label">Not Disclosed</div>'
            f'</div>', unsafe_allow_html=True,
        )
    with col4:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value">{result["elapsed_s"]}s</div>'
            f'<div class="metric-label">Fill Time</div>'
            f'</div>', unsafe_allow_html=True,
        )

    st.markdown(f"<br>", unsafe_allow_html=True)

    # Group by category
    by_category: dict[str, list] = {}
    for dp in result["datapoints"]:
        cat = dp.get("category", "Other")
        by_category.setdefault(cat, []).append(dp)

    for category, dps in by_category.items():
        st.markdown(f"**{category}**")

        header_html = (
            "<tr>"
            "<th style='width:30%'>ESRS ID / Label</th>"
            "<th style='width:20%'>Value</th>"
            "<th style='width:10%'>Unit</th>"
            "<th style='width:8%'>Page</th>"
            "<th style='width:8%'>Conf.</th>"
            "<th style='width:24%'>Source Text</th>"
            "</tr>"
        )

        rows_html = ""
        for dp in dps:
            badge = _confidence_badge(dp["confidence"], dp["status"])
            value_style = (
                "color:#166534;font-weight:600"
                if dp["status"] == "found"
                else "color:#9ca3af;font-style:italic"
            )
            src_text = dp.get("source_text", "")[:80]
            rows_html += (
                f"<tr>"
                f"<td><code style='font-size:0.72rem'>{dp['esrs_id']}</code><br>"
                f"<span style='font-size:0.8rem'>{dp['label']}</span></td>"
                f"<td style='{value_style}'>{dp['value']}</td>"
                f"<td style='font-family:monospace;font-size:0.8rem'>{dp['unit']}</td>"
                f"<td style='color:#6b7280'>p.{dp['source_page']}</td>"
                f"<td>{badge}</td>"
                f"<td style='font-size:0.75rem;color:#6b7280'>{src_text}{'…' if len(dp.get('source_text','')) > 80 else ''}</td>"
                f"</tr>"
            )

        st.markdown(
            f'<table class="compare-table"><thead>{header_html}</thead>'
            f'<tbody>{rows_html}</tbody></table><br>',
            unsafe_allow_html=True,
        )

    # ── Export ────────────────────────────────────────────────────────────────
    st.markdown("---")
    col_csv, col_json = st.columns(2)

    with col_csv:
        # Build CSV
        csv_lines = ["esrs_id,label,category,value,unit,source_page,confidence,status"]
        for dp in result["datapoints"]:
            csv_lines.append(
                f'{dp["esrs_id"]},{dp["label"]},{dp.get("category","")}'
                f',"{dp["value"]}",{dp["unit"]},{dp["source_page"]}'
                f',{dp["confidence"]},{dp["status"]}'
            )
        csv_str = "\n".join(csv_lines)
        st.download_button(
            "⬇ Export CSV",
            csv_str,
            file_name=f"csrd_e1_{result['company']}_{result['year']}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col_json:
        st.download_button(
            "⬇ Export JSON",
            json.dumps(result, indent=2),
            file_name=f"csrd_e1_{result['company']}_{result['year']}.json",
            mime="application/json",
            use_container_width=True,
        )
