"""DraftProof v2.0.0 — Main Multi-Page Streamlit Application Entrypoint (`streamlit_app.py`).

Follows all architectural invariants in `AGENTS.md`:
1. `st.set_page_config(...)` called first.
2. `render_traffic_offload_guard()` called immediately for <15ms offload card support (`?test_card=1`).
3. Lazy page imports inside the router after session state initialization.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="DraftProof — Plagiarism, Watermark & AI Footprint Removal Engine",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from draftproof.auth_persistence import ensure_session_auth_state
from draftproof.ui.common import inject_global_css, render_traffic_offload_guard

render_traffic_offload_guard()
ensure_session_auth_state(st)
inject_global_css()

PAGES = [
    ("humanizer", "🪄 Plagiarism & AI Remover"),
    ("code_humanizer", "<> Code Comment Humanizer"),
    ("citation", "❞ Citation Inserter & BIB/JSON"),
    ("checker", "⇄ Pairwise Document Similarity"),
    ("voice_watermark", "🧬 Voice Matcher & Watermark Lab"),
    ("feedback", "📖 Feature Request & Bug Reporter"),
]


def render_sidebar() -> str:
    """Render the DraftProof Hub navigation sidebar."""
    with st.sidebar:
        st.markdown("## DraftProof Hub")
        st.caption("Select Navigation Page:")

        current_page = st.session_state.get("active_page", "humanizer")
        for page_key, page_label in PAGES:
            is_active = current_page == page_key
            if st.button(
                page_label,
                key=f"nav_{page_key}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
            ):
                st.session_state["active_page"] = page_key
                st.rerun()

        st.markdown("---")
        logged_user = st.session_state.get("github_user", "local_developer")
        st.markdown(
            f"<div style='font-size:13px;color:#B0B8C8;margin-bottom:8px;'>"
            f"👤 Logged in as <strong style='color:#2ECC71;'>{logged_user}</strong> (Unlocked)</div>",
            unsafe_allow_html=True,
        )

        with st.expander("🔑 Switch GitHub / VIP Profile", expanded=False):
            new_user = st.text_input("GitHub Username or URL", value=logged_user)
            if st.button("Verify & Switch Profile", use_container_width=True):
                from draftproof.github_verifier import verify_github_support

                v_res = verify_github_support(new_user)
                if v_res.verified:
                    st.session_state["github_user"] = v_res.username
                    st.success(v_res.message)
                    st.rerun()

        st.markdown(
            """
            <div style="background:#181C26;border:1px solid rgba(255,255,255,0.09);border-radius:10px;padding:14px;margin-top:10px;font-size:13px;line-height:1.55;color:#D8DEE9;">
                <strong>🔔 What's New in v2.0.0:</strong>
                <ul style="padding-left:18px;margin:8px 0 0 0;">
                    <li><strong>38-Pattern AI Tell Scrubber</strong> &amp; Zero-Tell Invariant Gate</li>
                    <li><strong>2026 Watermark Assassin</strong> (Zero-Width Unicode, SynthID &amp; C2PA Stripper)</li>
                    <li><strong>Empirical Voice Matching Engine</strong></li>
                    <li><strong>Code Comment &amp; Docstring Humanizer</strong> (3 Developer Personas)</li>
                    <li><strong>Citation Inserter</strong> &amp; BibTeX / LaTeX / JSON Generator</li>
                    <li><strong>Turnitin Winnowing (k=5, w=4)</strong> &amp; ZipPy Perplexity Checker</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return str(st.session_state.get("active_page", "humanizer"))


active_route = render_sidebar()

if active_route == "humanizer":
    from draftproof.ui.humanizer_ui import render_humanizer_page

    render_humanizer_page()
elif active_route == "code_humanizer":
    from draftproof.ui.code_humanizer_ui import render_code_humanizer_page

    render_code_humanizer_page()
elif active_route == "citation":
    from draftproof.ui.citation_ui import render_citation_page

    render_citation_page()
elif active_route == "checker":
    from draftproof.ui.checker_ui import render_checker_page

    render_checker_page()
elif active_route == "voice_watermark":
    from draftproof.ui.voice_watermark_ui import render_voice_watermark_page

    render_voice_watermark_page()
elif active_route == "feedback":
    from draftproof.ui.feedback_ui import render_feedback_page

    render_feedback_page()
else:
    from draftproof.ui.humanizer_ui import render_humanizer_page

    render_humanizer_page()
