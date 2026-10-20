"""Page 6: Feature Request, Bug Reporter & Discipline Taxonomy Builder (`feedback_ui.py`).

Accessible at all times (bypasses any unlock gate as required by `ARCHITECTURE_RULES.md` §5).
Supports:
- Feature Requests, Bug Reports, and New Academic Discipline Taxonomy Requests
- Auto-generates a compliant `rules/academic/taxonomy/<discipline>/<subfield>.json`
  file containing the mandatory `__prompt__` metadata block!
- Generates pre-filled GitHub Issue URLs and downloadable report templates.
"""

from __future__ import annotations

import json
import urllib.parse

import streamlit as st

from draftproof.ui.common import render_footer, render_top_banner


def render_feedback_page() -> None:
    """Render the in-app Feature Request, Bug Reporter & Taxonomy Generator Hub."""
    render_top_banner("Feature Request, Bug Reporter & Discipline Taxonomy Hub")

    default_cat = st.session_state.get("feedback_default_category", "Feature Request")
    categories = [
        "Feature Request",
        "Bug Report",
        "New Academic Discipline Taxonomy Request",
    ]
    cat_idx = categories.index(default_cat) if default_cat in categories else 0

    col_form, col_info = st.columns([1.6, 1.0])

    with col_form:
        st.subheader("📬 Submit Feedback or Request a New Academic Field")
        category = st.selectbox("Submission Category", options=categories, index=cat_idx)
        title = st.text_input(
            "Title / Summary",
            placeholder="e.g., Add Quantum Information Science taxonomy or Report LaTeX macro edge case",
        )
        user_contact = st.text_input(
            "Your GitHub Handle or Email (Optional)",
            placeholder="@username or researcher@university.edu",
        )

        extra_taxonomy_json = None
        if category == "New Academic Discipline Taxonomy Request":
            st.markdown("##### 🏛️ Academic Discipline Taxonomy Specification")
            disc_name = st.text_input(
                "Discipline Category",
                value="Engineering & Physics",
            )
            subfield_name = st.text_input(
                "Sub-Field Name",
                value="Quantum Computing & Topological Qubits",
            )
            keywords_raw = st.text_input(
                "Core Keyword Triggers (comma-separated)",
                value="qubit, entanglement, decoherence, hamiltonian, unitary, fidelity, annealing",
            )
            journals_raw = st.text_input(
                "Prestigious Journals / Venues (comma-separated)",
                value="Physical Review Letters, Nature Physics, Quantum, npj Quantum Information",
            )
            authors_raw = st.text_input(
                "Representative Scholars (Last, Initials; semicolon-separated)",
                value="Preskill, J.; Shor, P. W.; Kitaev, A.; Cirac, J. I.",
            )

            kw_list = [k.strip().lower() for k in keywords_raw.split(",") if k.strip()]
            j_list = [j.strip() for j in journals_raw.split(",") if j.strip()]
            a_list = []
            for pair in authors_raw.split(";"):
                if "," in pair:
                    last, init = pair.split(",", 1)
                    a_list.append([last.strip(), init.strip()])
                elif pair.strip():
                    a_list.append([pair.strip(), "A."])

            subfield_id = "_".join(subfield_name.lower().split()[:3])
            taxonomy_payload = [
                {
                    "__prompt__": (
                        f"Role: Expert Academic Editor in {subfield_name}.\n"
                        f"Task: Define sub-fields, concepts, keyword triggers, author pools, and prestigious journals for {subfield_name}.\n"
                        "Negative Prompting (Strict Alignment):\n"
                        "- Do NOT include casual, non-academic, or informal terms."
                    )
                },
                {
                    "subfield_id": subfield_id or "custom_subfield",
                    "subfield_name": subfield_name,
                    "discipline": disc_name,
                    "keywords": kw_list,
                    "authors": a_list,
                    "journals": j_list,
                    "topics": [
                        f"quantitative modeling and experimental verification in {subfield_name.lower()}",
                        f"asymptotic error bounds and fault tolerance for {kw_list[0] if kw_list else 'quantum'} systems",
                    ],
                },
            ]
            extra_taxonomy_json = json.dumps(taxonomy_payload, indent=2)

        description = st.text_area(
            "Detailed Description / Steps to Reproduce",
            height=150,
            placeholder="Describe your feature idea, discipline requirements, or paste sample text that triggered an issue...",
        )

        if st.button("🚀 Generate Issue & Submission Package", type="primary", use_container_width=True):
            issue_title = f"[{category}] {title or 'DraftProof Feedback'}"
            issue_body = (
                f"### Category\n{category}\n\n"
                f"### Reporter\n{user_contact or 'Anonymous Researcher'}\n\n"
                f"### Description\n{description or 'See taxonomy specification below.'}\n"
            )
            if extra_taxonomy_json:
                issue_body += f"\n### Generated Taxonomy JSON (`ARCHITECTURE_RULES.md` Compliant)\n```json\n{extra_taxonomy_json}\n```\n"

            encoded_title = urllib.parse.quote(issue_title)
            encoded_body = urllib.parse.quote(issue_body)
            gh_url = (
                f"https://github.com/draftproof/DraftProof/issues/new"
                f"?title={encoded_title}&body={encoded_body}"
            )
            st.session_state["generated_feedback"] = {
                "title": issue_title,
                "body": issue_body,
                "gh_url": gh_url,
                "taxonomy_json": extra_taxonomy_json,
            }

        gen = st.session_state.get("generated_feedback")
        if gen:
            st.success("✅ Submission package ready!")
            st.markdown(
                f"👉 **[Click here to open pre-filled GitHub Issue]({gen['gh_url']})**"
            )
            if gen.get("taxonomy_json"):
                st.download_button(
                    "⬇️ Download ARCHITECTURE_RULES-Compliant Taxonomy JSON",
                    data=gen["taxonomy_json"].encode("utf-8"),
                    file_name="custom_discipline_taxonomy.json",
                    mime="application/json",
                    use_container_width=True,
                )
            with st.expander("Preview Formatted Issue Markdown", expanded=False):
                st.code(gen["body"], language="markdown")

    with col_info:
        st.subheader("🤝 Direct Developer Support")
        st.markdown(
            """
            <div class="telemetry-card">
                <div class="telemetry-label">GitHub Issue Tracker</div>
                <div style="font-size:15px;margin-top:6px;">
                    <a href="https://github.com/draftproof/DraftProof/issues" target="_blank" style="color:#FF6B6B;font-weight:700;">
                        🐛 Browse / Submit GitHub Issues →
                    </a>
                </div>
            </div>
            <div class="telemetry-card">
                <div class="telemetry-label">Architecture Guarantee</div>
                <div style="font-size:13.5px;color:#B0B8C8;margin-top:6px;line-height:1.5;">
                    All taxonomy JSON files include a strict <code>__prompt__</code> metadata header
                    and are dynamically loaded by <code>draftproof.core.rules</code> with zero hardcoded
                    word lists in Python code.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    render_footer()
