"""
app.py
------
ESG Assistant — main Streamlit application.

Run: streamlit run app.py
Dev: streamlit run app.py -- --dev (enables variant switcher)

Session state:
  messages      list of {role, content, metadata}
  doc_filters   dict {company, year} for scoped search
  config        loaded pipeline_config.yaml (mutable in dev mode)
  mode          "chat" | "compare"
"""

import sys
from pathlib import Path

import streamlit as st
import yaml

@st.cache_resource
def _init_qdrant():
    from esg_rag.store import get_store
    return get_store()

_init_qdrant()  # grab the lock once, hold it for the session
# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="ESG Assistant",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>

  /* Import fonts */
  @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

  /* Global */
  html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
  }

  /* Hide Streamlit branding */
  #MainMenu, footer, header { visibility: hidden; }

  /* Sidebar */
[data-testid="stSidebar"] {
    background: #0f1117;
    border-right: 1px solid #1e2530;
}
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 {
    font-family: 'DM Serif Display', serif;
    color: #7dd3a8 !important;
}

/* Hide ALL sidebar collapse/expand controls */
[data-testid="collapsedControl"] { display: none !important; }
[data-testid="stSidebarCollapseButton"] { display: none !important; }
button[kind="headerNoPadding"] { display: none !important; }

  /* Main title */
  .esg-title {
    font-family: 'DM Serif Display', serif;
    font-size: 2rem;
    color: #1a2e1a;
    margin-bottom: 0;
    letter-spacing: -0.5px;
  }
  .esg-subtitle {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.85rem;
    color: #6b7280;
    margin-top: 4px;
    font-weight: 300;
  }

  /* Chat messages */
  .user-bubble {
    background: #1a2e1a;
    color: #e2e8f0;
    border-radius: 16px 16px 4px 16px;
    padding: 12px 16px;
    margin: 8px 0;
    margin-left: 20%;
    font-size: 0.9rem;
    line-height: 1.5;
  }
  .assistant-bubble {
    background: #f8faf8;
    border: 1px solid #e2ebe2;
    border-radius: 4px 16px 16px 16px;
    padding: 14px 18px;
    margin: 8px 0;
    margin-right: 10%;
    font-size: 0.9rem;
    line-height: 1.6;
    color: #1f2937;
  }

  /* Citation badge */
  .citation-badge {
    display: inline-block;
    background: #dcfce7;
    color: #166534;
    border: 1px solid #86efac;
    border-radius: 6px;
    padding: 1px 7px;
    font-family: 'DM Mono', monospace;
    font-size: 0.72rem;
    margin: 0 2px;
    cursor: pointer;
    font-weight: 500;
  }

  /* Verifier badge */
  .verdict-pass { color: #16a34a; font-weight: 600; font-size: 0.78rem; }
  .verdict-warn { color: #d97706; font-weight: 600; font-size: 0.78rem; }
  .verdict-fail { color: #dc2626; font-weight: 600; font-size: 0.78rem; }

  /* Tool trace */
  .tool-chip {
    display: inline-block;
    background: #1e293b;
    color: #94a3b8;
    border-radius: 20px;
    padding: 2px 10px;
    font-family: 'DM Mono', monospace;
    font-size: 0.72rem;
    margin: 2px;
  }
  .tool-chip-retrieve { background: #172554; color: #93c5fd; }
  .tool-chip-compute  { background: #1a1a2e; color: #a78bfa; }
  .tool-chip-compare  { background: #1a2e1a; color: #6ee7b7; }

  /* Filter pill */
  .filter-pill {
    display: inline-block;
    background: #dcfce7;
    color: #166534;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 0.75rem;
    font-weight: 500;
    margin: 2px;
  }

  /* Metric card */
  .metric-card {
    background: #f8faf8;
    border: 1px solid #d1fae5;
    border-radius: 10px;
    padding: 10px 14px;
    text-align: center;
  }
  .metric-value {
    font-family: 'DM Serif Display', serif;
    font-size: 1.4rem;
    color: #166534;
  }
  .metric-label {
    font-size: 0.72rem;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  /* Input */
  .stTextInput input, .stTextArea textarea {
    border: 1.5px solid #d1fae5 !important;
    border-radius: 10px !important;
    font-family: 'DM Sans', sans-serif !important;
  }
  .stTextInput input:focus, .stTextArea textarea:focus {
    border-color: #16a34a !important;
    box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.1) !important;
  }

  /* Buttons */
  .stButton button {
    background: #166534 !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    transition: all 0.2s !important;
  }
  .stButton button:hover {
    background: #15803d !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(22, 163, 74, 0.3) !important;
  }

  /* Expander */
  .streamlit-expanderHeader {
    font-family: 'DM Mono', monospace;
    font-size: 0.8rem;
    color: #6b7280 !important;
  }

  /* Compare table */
  .compare-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }
  .compare-table th {
    background: #1a2e1a;
    color: #7dd3a8;
    padding: 8px 12px;
    text-align: left;
    font-family: 'DM Mono', monospace;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .compare-table td {
    padding: 8px 12px;
    border-bottom: 1px solid #e5e7eb;
  }
  .compare-table tr:hover td { background: #f0fdf4; }

  /* Cost panel */
  .cost-bar {
    height: 6px;
    background: #dcfce7;
    border-radius: 3px;
    overflow: hidden;
    margin: 4px 0;
  }
  .cost-fill {
    height: 100%;
    background: #16a34a;
    border-radius: 3px;
    transition: width 0.3s;
  }
</style>
""", unsafe_allow_html=True)


# ── Session state init ────────────────────────────────────────────────────────

def _init_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "doc_filters" not in st.session_state:
        st.session_state.doc_filters = {}
    if "config" not in st.session_state:
        cfg_path = Path("pipeline_config.yaml")
        st.session_state.config = (
            yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
        )
    if "mode" not in st.session_state:
        st.session_state.mode = "chat"
    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "csrd_result" not in st.session_state:
        st.session_state.csrd_result = None



_init_state()

# ── Dev mode ──────────────────────────────────────────────────────────────────

DEV_MODE = "dev" in sys.argv or st.query_params.get("dev") == "1"

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ESG Assistant")
    st.markdown("---")

    # Mode selector
    st.markdown("### Mode")
    mode = st.radio(
        "mode",
        ["Chat", "Compare", "CSRD"],
        label_visibility="collapsed",
    )
    if "Chat" in mode:
        st.session_state.mode = "chat"
    elif "Compare" in mode:
        st.session_state.mode = "compare"
    else:
        st.session_state.mode = "csrd"

    st.markdown("---")

    # Document library
    st.markdown("### Document Library")
    from components.doc_library import render_doc_library
    render_doc_library()

    st.markdown("---")

    # Cost panel
    from components.cost_panel import render_cost_panel
    render_cost_panel()

    # Dev mode variant switcher
    if DEV_MODE:
        st.markdown("---")
        st.markdown("### Dev — Pipeline Variant")
        variant = st.radio(
            "variant",
            ["dense_only", "dense+rerank", "hybrid", "orchestrated"],
            label_visibility="collapsed",
        )
        cfg = st.session_state.config
        cfg.setdefault("retrieval", {})
        cfg.setdefault("agent", {})
        cfg["retrieval"]["use_bm25"]    = "hybrid" in variant
        cfg["retrieval"]["use_reranker"] = "rerank" in variant or "hybrid" in variant
        cfg["agent"]["mode"]            = "orchestrated" if variant == "orchestrated" else "simple"
        st.session_state.config = cfg

# ── Main area ─────────────────────────────────────────────────────────────────

# Header
col_title, col_status = st.columns([3, 1])
with col_title:
    st.markdown('<div class="esg-title">ESG Intelligence Assistant</div>', unsafe_allow_html=True)
    filters = st.session_state.doc_filters
    if filters:
        pills = " ".join(
            f'<span class="filter-pill">{k}: {v}</span>'
            for k, v in filters.items()
        )
        st.markdown(f'<div style="margin-top:4px">{pills}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="esg-subtitle">51 reports indexed · 2022–2024 · 10 companies</div>', unsafe_allow_html=True)

with col_status:
    cfg = st.session_state.config
    agent_mode = cfg.get("agent", {}).get("mode", "simple")
    reranker   = cfg.get("retrieval", {}).get("use_reranker", False)
    st.markdown(
        f'<div style="text-align:right;margin-top:8px">'
        f'<span class="tool-chip">mode: {agent_mode}</span> '
        f'<span class="tool-chip">rerank: {"✓" if reranker else "✗"}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# Route to mode
if st.session_state.mode == "chat":
    from components.chat import render_chat
    render_chat()
elif st.session_state.mode == "compare":
    from components.compare_view import render_compare
    render_compare()
else:
    from components.csrd_view import render_csrd_view
    render_csrd_view()
