"""Page 4: Pairwise Document Similarity & Multi-Algorithm AI Checker (`checker_ui.py`).

Implements:
- Tab 1: 5-Signal AI Detector (ZipPy Compression Perplexity, Burstiness, Lexical Diversity,
  Stylometric Uniformity, 38-Pattern AI Tell Scanner) with Sentence-by-Sentence Heatmap
  and 1-Click Auto-Humanize Fixer.
- Tab 2: Turnitin Winnowing Pairwise Similarity Checker (k=5 word k-grams, Karp-Rabin rolling
  hash, window w=4 min-hash fingerprints, 8-word guarantee, Structural POS & Semantic Cosine)
  with downloadable `DraftProof_Checker_Reports_<TIMESTAMP>.zip`.
"""

from __future__ import annotations

import html
import json

import streamlit as st

from draftproof.ai_detector import analyze_ai_signals, compare_documents_winnowing
from draftproof.config import ConfigNamespace
from draftproof.core.doc_processor import create_checker_reports_zip, extract_text_from_docx_bytes
from draftproof.core.modifier import TextModifier
from draftproof.ui.common import render_footer, render_top_banner, render_visual_diff_html

SAMPLE_SOURCE_DOC = (
    "In this study, we analyze the numerical solution of the parabolic heat equation using the "
    "Crank-Nicolson finite difference scheme. Previous studies have shown that this implicit method "
    "is unconditionally stable with respect to the time step size and achieves second-order accuracy "
    "in both space and time. For the purpose of validation, three benchmark test cases were selected "
    "and compared against the analytical Fourier series solution."
)

SAMPLE_PARAPHRASED_DOC = (
    "Within the present manuscript, we scrutinize the computational solution of the parabolic heat equation "
    "through recourse to the Crank-Nicolson finite difference protocol. Prior investigations have substantiated "
    "that this implicit regimen remains unconditionally stable with regard to the temporal increment and "
    "attains second-order precision across spatial and temporal domains. Three benchmark test cases were "
    "selected with a view toward validation and appraised against the analytical Fourier series outcome."
)


def render_checker_page() -> None:
    """Render the Pairwise Document Similarity & Multi-Algorithm AI Checker page."""
    render_top_banner("Multi-Algorithm AI Detector & Turnitin Winnowing Similarity Checker")

    tab_ai, tab_sim = st.tabs(
        [
            "🛡️ 5-Signal AI Detector & 38-Pattern Tell Scanner",
            "⇄ Turnitin Winnowing Pairwise Similarity Checker (k=5, w=4)",
        ]
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 1: 5-SIGNAL AI DETECTOR & TELL SCANNER
    # ═══════════════════════════════════════════════════════════════════════════
    with tab_ai:
        if "checker_ai_input" not in st.session_state:
            st.session_state["checker_ai_input"] = (
                "In conclusion, it is important to delve into the comprehensive tapestry of modern neural networks. "
                "This study plays a pivotal role in illustrating that artificial intelligence stands as a testament "
                "to human innovation — providing a robust framework for future research."
            )

        ai_txt = st.text_area(
            "Paste Text to Audit for AI Signatures, Perplexity & Watermarks",
            value=st.session_state["checker_ai_input"],
            height=200,
        )
        st.session_state["checker_ai_input"] = ai_txt

        b_col1, b_col2 = st.columns(2)
        with b_col1:
            scan_ai_btn = st.button("🔍 Run 5-Signal AI Audit", type="primary", use_container_width=True)
        with b_col2:
            fix_ai_btn = st.button("⚡ Auto-Humanize & Fix All Flagged Tells", use_container_width=True)

        if fix_ai_btn and ai_txt.strip():
            cfg = ConfigNamespace({"style_preset": "conversational", "intensity": 80})
            cfg.apply_intensity(80)
            mod = TextModifier(config=cfg)
            fixed_txt = mod.modify_text(ai_txt)
            st.session_state["checker_ai_input"] = fixed_txt
            st.session_state["checker_ai_report"] = analyze_ai_signals(fixed_txt)
            st.rerun()

        if scan_ai_btn or "checker_ai_report" not in st.session_state:
            st.session_state["checker_ai_report"] = analyze_ai_signals(ai_txt)

        rep = st.session_state.get("checker_ai_report")
        if rep is not None and rep.word_count > 0:
            st.markdown(f"#### Verdict: **{rep.verdict}**")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Overall AI Risk", f"{rep.overall_ai_probability:.1f}%")
            c2.metric("Human Authenticity", f"{rep.human_authenticity_score:.1f}%")
            c3.metric("ZipPy Perplexity", f"{rep.compression_perplexity_score:.1f}/100")
            c4.metric("Burstiness Variance", f"{rep.burstiness_score:.1f}/100")
            c5.metric("Lexical Diversity (MATTR)", f"{rep.lexical_diversity_score:.1f}/100")

            st.markdown("##### 🎯 Sentence-by-Sentence AI Risk Heatmap")
            for s_item in rep.sentence_heatmap:
                css_cls = (
                    "risk-high"
                    if s_item.risk_level == "High"
                    else ("risk-moderate" if s_item.risk_level == "Moderate" else "risk-low")
                )
                badge = f"[{s_item.risk_level} Risk • {s_item.ai_risk_score:.0f}%]"
                reasons_str = "; ".join(s_item.reasons)
                st.markdown(
                    f"<div class='{css_cls}'><strong>{html.escape(badge)}</strong> "
                    f"{html.escape(s_item.sentence)}<br>"
                    f"<span style='font-size:12px;color:#B0B8C8;'>Signals: {html.escape(reasons_str)}</span></div>",
                    unsafe_allow_html=True,
                )

            if rep.detected_tells:
                st.markdown("##### 🚨 Detected 38-Pattern AI Tells & BERT Triggers")
                tell_rows = [
                    {
                        "Tell ID": t.tell_id,
                        "Category": t.category,
                        "Matched Trigger": t.matched_text,
                        "Deterministic Replacement": t.replacement or "(Contextual Rewrite)",
                    }
                    for t in rep.detected_tells
                ]
                st.dataframe(tell_rows, use_container_width=True, hide_index=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 2: TURNITIN WINNOWING PAIRWISE SIMILARITY CHECKER
    # ═══════════════════════════════════════════════════════════════════════════
    with tab_sim:
        st.markdown(
            "Compare a **Source Document** against a **Target / Paraphrased Document** across all three "
            "Turnitin verification layers: **Layer 1 (Winnowing k=5 / w=4 Karp-Rabin Fingerprints & 8-Word Guarantee)**, "
            "**Layer 2 (Syntactic Structure Skeleton)**, and **Layer 3 (Semantic Vector Alignment)**."
        )

        if "sim_source_txt" not in st.session_state:
            st.session_state["sim_source_txt"] = SAMPLE_SOURCE_DOC
        if "sim_target_txt" not in st.session_state:
            st.session_state["sim_target_txt"] = SAMPLE_PARAPHRASED_DOC

        sc_left, sc_right = st.columns(2)
        with sc_left:
            st.subheader("Source / Reference Document")
            src_doc = st.text_area(
                "Source Document Text",
                value=st.session_state["sim_source_txt"],
                height=240,
                key="sim_src_area",
            )
            st.session_state["sim_source_txt"] = src_doc
            src_up = st.file_uploader("Or upload Source .docx", type=["docx"], key="sim_src_docx")
            if src_up is not None:
                src_doc = extract_text_from_docx_bytes(src_up.read())

        with sc_right:
            st.subheader("Target / Humanized Document")
            tgt_doc = st.text_area(
                "Target Document Text",
                value=st.session_state["sim_target_txt"],
                height=240,
                key="sim_tgt_area",
            )
            st.session_state["sim_target_txt"] = tgt_doc
            tgt_up = st.file_uploader("Or upload Target .docx", type=["docx"], key="sim_tgt_docx")
            if tgt_up is not None:
                tgt_doc = extract_text_from_docx_bytes(tgt_up.read())

        if st.button("⇄ Run 3-Layer Winnowing Similarity Audit", type="primary", use_container_width=True):
            st.session_state["sim_last_report"] = compare_documents_winnowing(src_doc, tgt_doc)

        if "sim_last_report" not in st.session_state:
            st.session_state["sim_last_report"] = compare_documents_winnowing(src_doc, tgt_doc)

        s_rep = st.session_state.get("sim_last_report")
        if s_rep is not None:
            st.markdown(f"#### Evasion Verdict: **{s_rep.evasion_verdict}**")
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("Combined Similarity Index", f"{s_rep.combined_similarity_pct:.1f}%")
            k2.metric("Winnowing Fingerprint Match", f"{s_rep.winnowing_fingerprint_similarity_pct:.1f}%")
            k3.metric("Exact 5-Gram Overlap", f"{s_rep.exact_5gram_overlap_pct:.1f}%")
            k4.metric("8-Word Guarantee Hits", str(s_rep.guaranteed_8word_matches))
            k5.metric("Structural POS Similarity", f"{s_rep.structural_similarity_pct:.1f}%")

            if s_rep.flagged_passages:
                st.warning(
                    "🚨 Guaranteed 8+ Consecutive Word Matches Found: "
                    + " | ".join(f'"{p}"' for p in s_rep.flagged_passages)
                )
            elif s_rep.surviving_5grams:
                st.info(
                    "Surviving 5-gram windows: " + ", ".join(f'"{g}"' for g in s_rep.surviving_5grams[:10])
                )
            else:
                st.success("✅ Zero surviving 5-gram or 8-word contiguous chains between Source and Target!")

            with st.expander("🔍 Side-by-Side Lexical & Structural Diff", expanded=True):
                st.markdown(render_visual_diff_html(src_doc, tgt_doc), unsafe_allow_html=True)

            rep_json = json.dumps(s_rep.to_dict(), indent=2)
            z_name, z_bytes = create_checker_reports_zip(
                [
                    ("similarity_audit_report.json", rep_json),
                    ("source_document.txt", src_doc),
                    ("target_document.txt", tgt_doc),
                ]
            )
            st.download_button(
                label=f"📦 Download Audit Report Bundle ({z_name})",
                data=z_bytes,
                file_name=z_name,
                mime="application/zip",
                use_container_width=True,
            )

    render_footer()
