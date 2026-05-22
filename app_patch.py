"""
PATCH INSTRUCTIONS FOR app.py
==============================
Make these 3 changes to your existing app.py:

─────────────────────────────────────────────────────────────────────────
CHANGE 1: Mode selector — add CSRD tab
─────────────────────────────────────────────────────────────────────────

FIND:
    mode = st.radio(
        "mode",
        ["💬 Chat", "📊 Compare"],
        label_visibility="collapsed",
    )
    st.session_state.mode = "chat" if "Chat" in mode else "compare"

REPLACE WITH:
    mode = st.radio(
        "mode",
        ["💬 Chat", "📊 Compare", "📋 CSRD"],
        label_visibility="collapsed",
    )
    if "Chat" in mode:
        st.session_state.mode = "chat"
    elif "Compare" in mode:
        st.session_state.mode = "compare"
    else:
        st.session_state.mode = "csrd"

─────────────────────────────────────────────────────────────────────────
CHANGE 2: Session state init — add csrd_result
─────────────────────────────────────────────────────────────────────────

FIND:
    if "last_result" not in st.session_state:
        st.session_state.last_result = None

REPLACE WITH:
    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "csrd_result" not in st.session_state:
        st.session_state.csrd_result = None

─────────────────────────────────────────────────────────────────────────
CHANGE 3: Route to CSRD view
─────────────────────────────────────────────────────────────────────────

FIND:
    if st.session_state.mode == "chat":
        from components.chat import render_chat
        render_chat()
    else:
        from components.compare_view import render_compare
        render_compare()

REPLACE WITH:
    if st.session_state.mode == "chat":
        from components.chat import render_chat
        render_chat()
    elif st.session_state.mode == "compare":
        from components.compare_view import render_compare
        render_compare()
    else:
        from components.csrd_view import render_csrd_view
        render_csrd_view()
"""
