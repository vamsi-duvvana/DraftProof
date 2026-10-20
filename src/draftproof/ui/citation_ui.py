"""Page 3: Citation Inserter & BIB / JSON / LaTeX Reference Generator (`citation_ui.py`).

Implements:
- Unified `Citation Count` control (`Auto` or exact integer count)
- Hierarchical Academic Discipline Taxonomy selector (`Computer Science & AI`,
  `Engineering & Physics`, `Mathematics & Statistics`, `Quantitative Finance & Economics`,
  `Medical & Life Sciences`, `Auto-Detect Field`)
- In-app redirect button `"Don't see your Field of Study?"` -> navigates to Feedback page
- Multi-format export: Cited Text/DOCX, Formatted Bibliography, `citations.bib`,
  `citations.tex`, `citations.json`, and `DraftProof_Citations_<TIMESTAMP>.zip`
"""

from __future__ import annotations

from typing import Optional, Tuple

import streamlit as st

from draftproof.core.citation_engine import CitationEngine
from draftproof.core.doc_processor import create_citations_zip, process_docx_bytes
from draftproof.ui.common import render_copy_button, render_footer, render_top_banner

SAMPLE_CITATION_TEXT = (
    "Deep neural networks rely on stochastic gradient optimization to minimize non-convex loss landscapes. "
    "Transformer architectures utilize self-attention mechanisms to capture long-range dependencies across token sequences. "
    "Finite difference discretization of the parabolic heat equation requires careful step-size selection to guarantee numerical stability. "
    "Meanwhile, implied volatility surface calibration under stochastic volatility dynamics improves derivative pricing accuracy."
)


def render_citation_page() -> None:
    """Render the Citation Inserter & BIB/JSON/LaTeX Generator page."""
    render_top_banner("Auto-Citation Inserter & BibTeX / LaTeX / JSON Reference Generator")

    engine = CitationEngine()

    c1, c2, c3, c4 = st.columns([1.5, 1.2, 1.1, 1.3])
    with c1:
        discipline = st.selectbox(
            "Academic Field of Study (Taxonomy)",
            options=engine.list_disciplines(),
            index=0,
            help="Recursively scans rules/academic/taxonomy/ to match venues and authors to your research field.",
        )
    with c2:
        style = st.selectbox(
            "Citation Style Format",
            options=["IEEE [1]", "APA (Author, Year)", "LaTeX \\cite{key}"],
            index=0,
        )
    with c3:
        citation_count = st.selectbox(
            "Citation Count",
            options=["Auto", "1", "2", "3", "5", "8", "10", "15", "20", "30", "50"],
            index=0,
            help="Contextual auto-detection ('Auto') or exact integer citation count.",
        )
    with c4:
        st.markdown("<div style='height:26px;'></div>", unsafe_allow_html=True)
        if st.button("➕ Don't see your Field of Study?", use_container_width=True):
            st.session_state["feedback_default_category"] = "New Academic Discipline Taxonomy Request"
            st.session_state["active_page"] = "feedback"
            st.rerun()

    if "citation_input_text" not in st.session_state:
        st.session_state["citation_input_text"] = SAMPLE_CITATION_TEXT
    if "citation_last_result" not in st.session_state:
        st.session_state["citation_last_result"] = None

    c_sample, _ = st.columns([1.5, 4.5])
    with c_sample:
        if st.button("📚 Load Multi-Disciplinary Research Sample", use_container_width=True):
            st.session_state["citation_input_text"] = SAMPLE_CITATION_TEXT
            st.session_state["cite_src_area"] = SAMPLE_CITATION_TEXT
            st.rerun()

    col_in, col_out = st.columns(2)
    with col_in:
        st.subheader("Source Manuscript / Draft")
        src_text = st.text_area(
            "Input Text for Citation Placement",
            value=st.session_state["citation_input_text"],
            height=280,
            key="cite_src_area",
        )
        st.session_state["citation_input_text"] = src_text
        uploaded_docx = st.file_uploader(
            "Or Upload Word Document (.docx) for In-Place Citation Insertion",
            type=["docx"],
            key="cite_docx_upload",
        )
        gen_cites_btn = st.button(
            "❞ Insert Contextual Citations & Generate Bibliography",
            type="primary",
            use_container_width=True,
        )

    with col_out:
        st.subheader("Cited Manuscript Output")
        last_res = st.session_state.get("citation_last_result")
        cited_out = last_res["result"].cited_text if last_res else ""
        st.text_area(
            "Cited Text Output",
            value=cited_out,
            height=280,
            placeholder="Text with contextual citations will appear here...",
        )
        render_copy_button(cited_out, "📋 Copy Cited Text", key="copy_cited_txt")

    if gen_cites_btn:
        docx_item: Optional[Tuple[str, bytes]] = None
        target_text = src_text
        if uploaded_docx is not None:
            raw_docx = uploaded_docx.read()
            # Run citation insertion on paragraphs in-place
            para_counter = {"idx": 0}
            c_res_preview = engine.insert_citations(
                src_text or SAMPLE_CITATION_TEXT,
                style=style,
                count=citation_count,
                discipline=discipline,
            )

            def _cite_para_cb(p_txt: str, sec: Optional[str] = None) -> str:
                if len(p_txt.strip()) < 45:
                    return p_txt
                sub_res = engine.insert_citations(
                    p_txt, style=style, count="1", discipline=discipline
                )
                para_counter["idx"] += sub_res.citations_inserted
                return sub_res.cited_text

            d_proc = process_docx_bytes(raw_docx, _cite_para_cb, filename=uploaded_docx.name)
            docx_item = (f"Cited_{uploaded_docx.name}", d_proc.output_bytes)
            target_text = d_proc.extracted_before_text or src_text

        c_res = engine.insert_citations(
            target_text,
            style=style,
            count=citation_count,
            discipline=discipline,
        )
        zip_name, zip_bytes = create_citations_zip(
            cited_text=c_res.cited_text,
            bibtex_str=c_res.bibtex_content,
            latex_str=c_res.latex_bibitem_content,
            json_str=c_res.json_content,
            formatted_bib=c_res.formatted_bibliography,
            docx_item=docx_item,
        )
        st.session_state["citation_last_result"] = {
            "result": c_res,
            "zip_name": zip_name,
            "zip_bytes": zip_bytes,
            "docx_item": docx_item,
        }
        st.rerun()

    last_res = st.session_state.get("citation_last_result")
    if last_res is not None:
        c_res = last_res["result"]
        st.markdown("---")
        m1, m2, m3 = st.columns(3)
        m1.metric("Detected Discipline Taxonomy", c_res.detected_discipline)
        m2.metric("Citations Inserted", str(c_res.citations_inserted))
        m3.metric("Citation Format", c_res.style)

        st.download_button(
            label=f"📦 Download Complete Reference Package ({last_res['zip_name']})",
            data=last_res["zip_bytes"],
            file_name=last_res["zip_name"],
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )

        t_bib, t_bibtex, t_latex, t_json = st.tabs(
            [
                "📜 Formatted References",
                "🔖 BibTeX (citations.bib)",
                "📐 LaTeX (\\bibitem)",
                "🗂️ Structured JSON (citations.json)",
            ]
        )
        with t_bib:
            st.markdown(c_res.formatted_bibliography or "*No references generated.*")
        with t_bibtex:
            st.code(c_res.bibtex_content, language="bibtex")
            st.download_button(
                "⬇️ Download citations.bib",
                data=c_res.bibtex_content.encode("utf-8"),
                file_name="citations.bib",
                mime="text/plain",
            )
        with t_latex:
            st.code(c_res.latex_bibitem_content, language="latex")
            st.download_button(
                "⬇️ Download citations.tex",
                data=c_res.latex_bibitem_content.encode("utf-8"),
                file_name="citations.tex",
                mime="text/plain",
            )
        with t_json:
            st.code(c_res.json_content, language="json")
            st.download_button(
                "⬇️ Download citations.json",
                data=c_res.json_content.encode("utf-8"),
                file_name="citations.json",
                mime="application/json",
            )

    render_footer()
