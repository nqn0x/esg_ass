"""
components/compare_view.py
--------------------------
Cross-document comparison view.
User selects metric + companies → compare_documents tool → table.
"""

from __future__ import annotations

import streamlit as st


def render_compare() -> None:
    st.markdown("### ⚖️ Document Comparison")
    st.markdown("Compare a specific ESG metric across companies.")

    from esg_rag.store import get_store
    docs  = get_store().list_docs()
    companies = sorted(set(d["company"] for d in docs))
    years     = sorted(set(d["year"] for d in docs), reverse=True)

    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        metric = st.text_input(
            "Metric to compare",
            placeholder="e.g. Scope 1 GHG emissions, water consumption, renewable energy %",
        )
    with col2:
        selected_companies = st.multiselect(
            "Companies (leave empty for all)",
            companies,
        )
    with col3:
        selected_year = st.selectbox("Year", ["All"] + years)

    if st.button("Compare →", use_container_width=True) and metric:
        with st.spinner("Comparing across reports…"):
            from esg_rag.tools import load_all, call_tool
            import yaml
            from pathlib import Path
            cfg = yaml.safe_load(Path("pipeline_config.yaml").read_text())
            cfg["agent"]["tools"]["compare_documents"] = True
            load_all(cfg)

            result = call_tool("compare_documents", {
                "metric_query": metric,
                "companies":    selected_companies or None,
                "year":         selected_year if selected_year != "All" else None,
            })

        if "error" in result:
            st.error(result["error"])
            return

        rows = result.get("rows", [])
        if not rows:
            st.warning("No data found for this metric.")
            return

        st.markdown(f"**{result['metric_query']}** — {result['n_companies']} companies")

        # Build HTML table
        header_html = "".join(
            f"<th>{h.replace('_', ' ').title()}</th>"
            for h in ["company", "year", "value", "unit", "source_page"]
        )

        rows_html = ""
        for row in rows:
            val = row.get("value", "not disclosed")
            is_missing = val in ("not found", "not disclosed", "")
            val_style = "color:#9ca3af" if is_missing else "color:#166534;font-weight:600"

            rows_html += (
                f"<tr>"
                f"<td><strong>{row.get('company','')}</strong></td>"
                f"<td>{row.get('year','')}</td>"
                f"<td style='{val_style}'>{val}</td>"
                f"<td style='color:#6b7280;font-family:monospace;font-size:0.8em'>{row.get('unit','')}</td>"
                f"<td style='color:#6b7280'>p.{row.get('source_page','')}</td>"
                f"</tr>"
            )

        st.markdown(
            f'<table class="compare-table"><thead><tr>{header_html}</tr></thead>'
            f'<tbody>{rows_html}</tbody></table>',
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.markdown("**Source excerpts:**")
        for row in rows[:5]:
            if row.get("source_text"):
                with st.expander(f"{row['company']} {row['year']} p.{row.get('source_page','')}"):
                    st.markdown(
                        f'<div style="font-size:0.82rem;color:#374151">{row["source_text"]}</div>',
                        unsafe_allow_html=True,
                    )
