"""
components/doc_library.py
--------------------------
Sidebar document library:
  - Lists all indexed docs grouped by company
  - Checkboxes write to st.session_state.doc_filters
  - Year filter dropdown
  - Chunk count display
"""

from __future__ import annotations

import streamlit as st


@st.cache_resource
def _get_store_cached():
    from esg_rag.store import get_store
    return get_store()

def _get_docs() -> list[dict]:
    return _get_store_cached().list_docs()

def render_doc_library() -> None:
    docs = _get_docs()
    if not docs:
        st.caption("No documents indexed yet.")
        return

    # Year filter
    years = sorted(set(d["year"] for d in docs), reverse=True)
    selected_year = st.selectbox(
        "Filter by year",
        ["All years"] + years,
        label_visibility="collapsed",
    )

    # Filter docs
    filtered = docs if selected_year == "All years" else [
        d for d in docs if d["year"] == selected_year
    ]

    # Group by company
    by_company: dict[str, list] = {}
    for d in filtered:
        by_company.setdefault(d["company"], []).append(d)

    # Company checkboxes
    selected_company = st.session_state.doc_filters.get("company")
    st.caption(f"{len(filtered)} reports · {len(by_company)} companies")

    new_company = None
    for company in sorted(by_company.keys()):
        reports = by_company[company]
        n_chunks = sum(r["n_chunks"] for r in reports)
        years_str = ", ".join(sorted(r["year"] for r in reports))

        checked = st.checkbox(
            f"**{company}** · {years_str}",
            value=(company == selected_company),
            key=f"doc_{company}",
            help=f"{n_chunks:,} chunks indexed",
        )
        if checked:
            new_company = company

    # Update filters
    if new_company:
        st.session_state.doc_filters = {"company": new_company}
        if selected_year != "All years":
            st.session_state.doc_filters["year"] = selected_year
    else:
        st.session_state.doc_filters = {}
        if selected_year != "All years":
            st.session_state.doc_filters["year"] = selected_year

    # Clear filter button
    if st.session_state.doc_filters:
        if st.button("✕ Clear filters", key="clear_filters"):
            st.session_state.doc_filters = {}
            st.rerun()
