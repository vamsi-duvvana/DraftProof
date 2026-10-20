"""Page 1: Plagiarism & AI Remover (`src/draftproof/ui/humanizer_ui.py`).

Matches the official DraftProof studio layout and adds:
- Sample benchmark loaders (Academic Abstract, College Essay, LaTeX Paper, Watermarked Text)
- Full 19-stage pipeline & safety invariant gate controls
- Empirical Voice Profile integration
- Interactive Word-Level Visual Diff Viewer
- Live Before/After 5-Signal AI Detection & Turnitin Winnowing K-Gram Telemetry
- Multi-File & ZIP Batch Document Processor (.docx, .tex, .md, .txt, .zip) with C2PA stripping
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import streamlit as st

from draftproof.ai_detector import analyze_ai_signals, compare_documents_winnowing
from draftproof.config import ConfigNamespace
from draftproof.core.citation_engine import CitationEngine
from draftproof.core.code_comment_parser import CodeCommentHumanizer
from draftproof.core.doc_processor import (
    create_humanized_docs_zip,
    process_docx_bytes,
    process_zip_archive_bytes,
)
from draftproof.core.modifier import TextModifier
from draftproof.core.parser import process_latex_document
from draftproof.core.voice_matcher import VoiceProfile, apply_voice_profile_to_config
from draftproof.ui.common import (
    render_copy_button,
    render_footer,
    render_top_banner,
    render_visual_diff_html,
)

SAMPLE_ACADEMIC_ABSTRACT = (
    "In conclusion, it is important to delve into the comprehensive tapestry of modern neural networks. "
    "This study plays a pivotal role in illustrating that artificial intelligence stands as a testament "
    "to human innovation. Furthermore, the interplay between stochastic optimization and computational "
    "scalability provides a robust framework for subsequent empirical inquiries. Previous studies have shown "
    "that the convergence of gradient descent is proportional to the learning rate schedule."
)

SAMPLE_COLLEGE_ESSAY = (
    "Moreover, in today's fast-paced digital era, the profound impact of social connectivity cannot be "
    "overlooked. This experience serves as a critical milestone in my personal journey. Furthermore, it "
    "allows us to delve deep into the multifaceted dimensions of human empathy — fostering a sense of "
    "community. Ultimately, this paradigm shift has fundamentally shaped my worldview."
)

SAMPLE_LATEX_MANUSCRIPT = r"""\documentclass{article}
\begin{document}
\begin{abstract}
In this paper, we delve into the numerical solution of the heat equation using the Crank-Nicolson method. Previous studies have shown that this approach plays a pivotal role in ensuring stability for $\Delta t \le 0.05$.
\end{abstract}

\section{Methodology}
Using the finite difference method, we solved the partial differential equation on a uniform mesh with $N = 256$ grid nodes:
\begin{equation}
\frac{\partial u}{\partial t} = \alpha \frac{\partial^2 u}{\partial x^2}
\end{equation}
Furthermore, the results indicate a significant increase in accuracy when compared with explicit schemes \cite{smith2022heat}.
\end{document}"""

SAMPLE_WATERMARKED_TEXT = (
    "Certainly! Here is a comprehensive overview of the topic. "
    "Artificial\u200b intelligence\u200c stands as a testament\u200d to modern engineering — "
    "playing a pivotal role in how researchers\u2060 delve into complex datasets. "
    "Moreover, the interplay between hardware acceleration and algorithmic efficiency "
    "provides a robust framework for 98.5% accuracy [1]. I hope this helps!"
)


def _count_words_chars(text: str) -> Tuple[int, int]:
    if not text or not text.strip():
        return 0, 0
    return len(text.split()), len(text)


def render_humanizer_page() -> None:
    """Render the Plagiarism & AI Remover studio page."""
    render_top_banner("Intelligent Similarity Evasion & Multi-Algorithm Checker")

    # Top 5-Column Control Bar
    c1, c2, c3, c4, c5 = st.columns([1.15, 1.35, 1.4, 1.25, 1.0])
    with c1:
        format_sel = st.selectbox(
            "Format Selection",
            options=[
                "Auto-Detect",
                "Plain Text (.txt)",
                "Academic LaTeX (.tex)",
                "Markdown (.md)",
                "Source Code",
            ],
            index=0,
            help="Automatically detects plain text, LaTeX math manuscripts, Markdown, or source code.",
        )
    with c2:
        style_preset_label = st.selectbox(
            "Style Preset",
            options=[
                "Conversational / Daily English",
                "Academic / Scholarly",
                "Technical / Dense",
            ],
            index=0,
            help="Selects the decoupled JSON rule repository (Conversational vs Academic/Technical).",
        )
    with c3:
        intensity = st.slider(
            "Humanizing Intensity",
            min_value=0,
            max_value=100,
            value=75,
            step=5,
            help="Non-linear power curve controlling transformation aggressiveness across all 19 stages.",
        )
    with c4:
        code_mode_preset = st.selectbox(
            "Code Mode Preset",
            options=[
                "Off (Document Mode)",
                "🐣 Beginner Developer",
                "⚙️ Intermediate Developer",
                "👨‍💻 Senior Architect / Expert",
            ],
            index=0,
            help="When enabled or when Source Code is detected, humanizes only code comments & docstrings.",
        )
    with c5:
        insert_citations = st.selectbox(
            "Insert Citations",
            options=["Off", "IEEE [1]", "APA (Author, Year)", "LaTeX \\cite{}"],
            index=0,
            help="Optionally inject contextual academic references with section-aware shielding.",
        )

    is_academic_mode = "Academic" in style_preset_label or "Technical" in style_preset_label
    preset_key = "academic" if is_academic_mode else "conversational"

    # Advanced 19-Stage Pipeline & Safety Gate Controls
    with st.expander("⚙️ Advanced 19-Stage Pipeline, Safety Invariant Gates & Voice Matcher", expanded=False):
        adv1, adv2, adv3, adv4 = st.columns(4)
        with adv1:
            st.markdown("**🛡️ Threat & Invariant Gates**")
            en_scrubber = st.checkbox("38-Pattern AI Tell Scrubber", value=True)
            en_zw = st.checkbox("Purge Zero-Width & Homoglyphs", value=True)
            en_tell_gate = st.checkbox("Zero-Tell Gate (tells_out ≤ tells_in)", value=True)
            en_fact_gate = st.checkbox("Fact & Number Preservation Gate", value=True)
        with adv2:
            st.markdown("**🧬 Lexical & N-Gram Stages**")
            en_phrases = st.checkbox("Multi-Word Phrase Rewrites", value=True)
            en_synonyms = st.checkbox("Morphological Synonym Swaps", value=True)
            en_determiners = st.checkbox("Determiner Cycle Memory", value=True)
            en_ngram_audit = st.checkbox("Smart Similarity Shield (5-Gram Audit)", value=True)
        with adv3:
            st.markdown("**🏗️ Structural Syntax Tree Stages**")
            en_voice = st.checkbox("Active ↔ Passive Voice Inversion", value=True)
            en_fusion = st.checkbox("Sentence Fusion (Burstiness)", value=True)
            en_split = st.checkbox("Compound Sentence Splitting", value=True)
            en_nominal = st.checkbox("Switch Verb & Noun Forms", value=is_academic_mode)
        with adv4:
            st.markdown("**🔄 Discourse & Clause Stages**")
            en_discourse = st.checkbox("PDTB 2.0 Discourse Rotation", value=True)
            en_transitions = st.checkbox("Transition Phrase Injection", value=True)
            en_reorder = st.checkbox("Clause & Preposition Reordering", value=True)
            en_appositive = st.checkbox(
                "Add Explanatory Details (Appositives)",
                value=(not is_academic_mode),
                help="Injects domain definitions once per term (disabled by default in dense Academic preset).",
            )
            en_coord = st.checkbox("Same-Subject Clause Coordination", value=True)

        use_voice_profile = False
        active_vp: VoiceProfile | None = st.session_state.get("active_voice_profile")
        if active_vp is not None:
            use_voice_profile = st.checkbox(
                f"🎙️ Apply Empirical Voice Profile (Mean Sentence: {active_vp.mean_sentence_length}w, Burstiness: {active_vp.burstiness_index})",
                value=True,
            )

    # Build ConfigNamespace from UI controls
    cfg = ConfigNamespace(
        {
            "style_preset": preset_key,
            "intensity": intensity,
            "insert_citations": insert_citations,
            "enable_ai_tell_scrubber": en_scrubber,
            "enable_zero_width_purge": en_zw,
            "enable_tell_invariant_gate": en_tell_gate,
            "enable_fact_invariant_gate": en_fact_gate,
            "enable_phrase_rewrites": en_phrases,
            "enable_synonym_swap": en_synonyms,
            "enable_determiner_swap": en_determiners,
            "enable_ngram_audit": en_ngram_audit,
            "enable_voice_transform": en_voice,
            "enable_sentence_fusion": en_fusion,
            "enable_sentence_split": en_split,
            "enable_nominalization": en_nominal,
            "enable_discourse_rotate": en_discourse,
            "enable_transition_inject": en_transitions,
            "enable_word_reorder": en_reorder,
            "enable_clause_reorder": en_reorder,
            "enable_appositive": en_appositive,
            "enable_subject_coordination": en_coord,
        }
    )
    cfg.apply_intensity(intensity)
    if use_voice_profile and active_vp is not None:
        apply_voice_profile_to_config(active_vp, cfg)

    tab_text, tab_doc = st.tabs(
        ["✏️ Text & LaTeX Checker", "📄 Document & Batch ZIP Checker (.docx, .tex, .md, .zip)"]
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 1: TEXT & LATEX STUDIO
    # ═══════════════════════════════════════════════════════════════════════════
    with tab_text:
        if "humanizer_input_text" not in st.session_state:
            st.session_state["humanizer_input_text"] = ""
        if "humanizer_output_text" not in st.session_state:
            st.session_state["humanizer_output_text"] = ""
        if "humanizer_last_telemetry" not in st.session_state:
            st.session_state["humanizer_last_telemetry"] = None

        # Sample loader bar
        s_col0, s_col1, s_col2, s_col3, s_col4 = st.columns([1.1, 1.3, 1.3, 1.3, 1.5])
        with s_col0:
            st.markdown("<div style='padding-top:6px;font-size:13px;color:#9DA5B4;'>⚡ Quick Samples:</div>", unsafe_allow_html=True)
        with s_col1:
            if st.button("📄 Academic Abstract", use_container_width=True):
                st.session_state["humanizer_input_text"] = SAMPLE_ACADEMIC_ABSTRACT
                st.session_state["orig_text_widget"] = SAMPLE_ACADEMIC_ABSTRACT
                st.rerun()
        with s_col2:
            if st.button("✍️ College Essay", use_container_width=True):
                st.session_state["humanizer_input_text"] = SAMPLE_COLLEGE_ESSAY
                st.session_state["orig_text_widget"] = SAMPLE_COLLEGE_ESSAY
                st.rerun()
        with s_col3:
            if st.button("📐 LaTeX Paper ($...$)", use_container_width=True):
                st.session_state["humanizer_input_text"] = SAMPLE_LATEX_MANUSCRIPT
                st.session_state["orig_text_widget"] = SAMPLE_LATEX_MANUSCRIPT
                st.rerun()
        with s_col4:
            if st.button("🚨 Watermarked + AI Tells", use_container_width=True):
                st.session_state["humanizer_input_text"] = SAMPLE_WATERMARKED_TEXT
                st.session_state["orig_text_widget"] = SAMPLE_WATERMARKED_TEXT
                st.rerun()
        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("Original Text")
            input_text = st.text_area(
                "Original Text Area",
                value=st.session_state["humanizer_input_text"],
                height=320,
                placeholder="Paste your text, LaTeX manuscript, or code here...",
            )
            st.session_state["humanizer_input_text"] = input_text
            in_words, in_chars = _count_words_chars(input_text)
            st.markdown(
                f"<div class='counter-caption'>Words: {in_words} | Characters: {in_chars}</div>",
                unsafe_allow_html=True,
            )
            humanize_clicked = st.button(
                "🪄 Humanize Text",
                type="primary",
                use_container_width=True,
            )

        with col_right:
            st.subheader("Humanized & Evaded Text")
            output_val = st.text_area(
                "Output Text Area",
                value=st.session_state["humanizer_output_text"],
                height=320,
                placeholder="Humanized text will appear here...",
            )
            st.session_state["humanizer_output_text"] = output_val
            out_words, out_chars = _count_words_chars(output_val)
            c_cnt, c_cpy = st.columns([2, 1])
            with c_cnt:
                st.markdown(
                    f"<div class='counter-caption'>Words: {out_words} | Characters: {out_chars}</div>",
                    unsafe_allow_html=True,
                )
            with c_cpy:
                render_copy_button(output_val, "📋 Copy Output", key="humanizer_out_copy")

            if st.button("🗑️ Clear All", use_container_width=True):
                st.session_state["humanizer_input_text"] = ""
                st.session_state["orig_text_widget"] = ""
                st.session_state["humanizer_output_text"] = ""
                st.session_state["humanizer_last_telemetry"] = None
                st.rerun()

        if humanize_clicked and input_text.strip():
            # Determine execution mode (Code Mode vs LaTeX vs Document/Text Mode)
            is_code = (
                code_mode_preset != "Off (Document Mode)"
                or format_sel == "Source Code"
            )
            is_latex = (
                format_sel == "Academic LaTeX (.tex)"
                or ("\\begin{" in input_text or "\\section{" in input_text or "\\documentclass" in input_text)
            )

            if is_code:
                persona_choice = (
                    "intermediate"
                    if code_mode_preset == "Off (Document Mode)"
                    else code_mode_preset
                )
                code_engine = CodeCommentHumanizer(
                    persona=persona_choice,
                    intensity=intensity,
                )
                code_res = code_engine.humanize_code(input_text)
                final_text = code_res.humanized_code
                telemetry_dict = code_engine.modifier.get_telemetry_summary()
                telemetry_dict["Comments Modified"] = code_res.comments_modified
                telemetry_dict["Docstrings Converted"] = code_res.docstrings_converted
            else:
                modifier = TextModifier(config=cfg)
                cite_engine = CitationEngine() if insert_citations != "Off" else None
                if is_latex:
                    final_text = process_latex_document(input_text, modifier)
                    if cite_engine is not None:
                        c_res = cite_engine.insert_citations(final_text, style=insert_citations)
                        final_text = c_res.cited_text
                        modifier.citation_insert_count += c_res.citations_inserted
                else:
                    final_text = modifier.modify_text(input_text, citation_engine=cite_engine)
                telemetry_dict = modifier.get_telemetry_summary()

            before_ai = analyze_ai_signals(input_text)
            after_ai = analyze_ai_signals(final_text)
            sim_report = compare_documents_winnowing(input_text, final_text)

            st.session_state["humanizer_output_text"] = final_text
            st.session_state["humanizer_last_telemetry"] = {
                "before_text": input_text,
                "after_text": final_text,
                "before_ai": before_ai,
                "after_ai": after_ai,
                "sim_report": sim_report,
                "stage_counts": telemetry_dict,
            }
            st.rerun()

        # Render Telemetry & Visual Diff if available
        tele = st.session_state.get("humanizer_last_telemetry")
        if tele is not None:
            st.markdown("---")
            st.markdown("### 🛡️ Evasion & Transformation Telemetry")
            before_ai = tele["before_ai"]
            after_ai = tele["after_ai"]
            sim_rep = tele["sim_report"]
            stage_counts: Dict[str, int] = tele["stage_counts"]

            m1, m2, m3, m4, m5 = st.columns(5)
            ai_delta = round(after_ai.overall_ai_probability - before_ai.overall_ai_probability, 1)
            m1.metric(
                "Estimated AI Risk",
                f"{after_ai.overall_ai_probability:.1f}%",
                delta=f"{ai_delta:+.1f}% (from {before_ai.overall_ai_probability:.1f}%)",
                delta_color="inverse",
            )
            m2.metric(
                "Winnowing k=5 Similarity",
                f"{sim_rep.combined_similarity_pct:.1f}%",
                delta=f"{sim_rep.guaranteed_8word_matches} 8-word chains",
                delta_color="off",
            )
            perp_delta = round(
                after_ai.compression_perplexity_score - before_ai.compression_perplexity_score, 1
            )
            m3.metric(
                "ZipPy Perplexity",
                f"{after_ai.compression_perplexity_score:.1f}/100",
                delta=f"{perp_delta:+.1f}",
            )
            burst_delta = round(after_ai.burstiness_score - before_ai.burstiness_score, 1)
            m4.metric(
                "Burstiness Score",
                f"{after_ai.burstiness_score:.1f}/100",
                delta=f"{burst_delta:+.1f}",
            )
            m5.metric(
                "Total Transformations",
                str(stage_counts.get("Total Transformations", 0)),
                delta=f"{stage_counts.get('AI Tells Scrubbed', 0)} AI tells scrubbed",
            )

            with st.expander("🔍 Interactive Word-Level Visual Diff (Original vs Humanized)", expanded=True):
                st.caption(
                    "Red strikethrough indicates removed AI tells and source k-grams; green highlight indicates deterministic replacements."
                )
                diff_html = render_visual_diff_html(tele["before_text"], tele["after_text"])
                st.markdown(diff_html, unsafe_allow_html=True)

            with st.expander("📊 19-Stage Pipeline Execution Breakdown", expanded=False):
                non_zero = [
                    {"Transformation Stage": k, "Count": v}
                    for k, v in stage_counts.items()
                    if k != "Total Transformations"
                ]
                st.dataframe(non_zero, use_container_width=True, hide_index=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 2: DOCUMENT & BATCH ZIP PROCESSOR (.docx, .tex, .md, .txt, .zip)
    # ═══════════════════════════════════════════════════════════════════════════
    with tab_doc:
        st.markdown(
            "#### 📦 Multi-Format In-Place Document & Archive Processor\n"
            "Upload one or multiple **Word (`.docx`)**, **LaTeX (`.tex`)**, **Markdown (`.md`)**, "
            "**Plain Text (`.txt`)**, or **Archive (`.zip`)** files. XML run formatting, bold/italics, "
            "tables, equations, headers, and folder hierarchies remain **100% preserved**, while hidden "
            "**C2PA metadata** is automatically stripped."
        )

        uploaded_files = st.file_uploader(
            "Upload Documents or Archives (.docx, .tex, .md, .txt, .zip)",
            type=["docx", "tex", "md", "txt", "zip"],
            accept_multiple_files=True,
            key="doc_batch_uploader",
        )

        if uploaded_files:
            if st.button("🚀 Process & Humanize Uploaded Files", type="primary", use_container_width=True):
                bundle_outputs: List[Tuple[str, bytes | str]] = []
                file_summaries: List[Dict[str, Any]] = []
                preview_diffs: List[Tuple[str, str, str]] = []

                for up_file in uploaded_files:
                    fname = up_file.name
                    raw_bytes = up_file.read()
                    ext = Path(fname).suffix.lower()
                    mod = TextModifier(config=cfg)
                    c_eng = CitationEngine() if insert_citations != "Off" else None

                    if ext == ".docx":
                        def _docx_line_cb(line_txt: str, sec_name: str | None = None) -> str:
                            return mod.modify_line(line_txt, section_name=sec_name or "body")

                        d_res = process_docx_bytes(raw_bytes, _docx_line_cb, filename=fname, strip_c2pa=True)
                        out_name = f"Humanized_{fname}"
                        bundle_outputs.append((out_name, d_res.output_bytes))
                        file_summaries.append(
                            {
                                "File": fname,
                                "Format": "Word (.docx)",
                                "Details": f"{d_res.paragraphs_modified} paragraphs & {d_res.tables_modified} tables humanized; C2PA stripped",
                                "Transformations": mod.get_telemetry_summary()["Total Transformations"],
                            }
                        )
                        preview_diffs.append((fname, d_res.extracted_before_text, d_res.extracted_after_text))

                    elif ext == ".tex":
                        tex_in = raw_bytes.decode("utf-8", errors="replace")
                        tex_out = process_latex_document(tex_in, mod)
                        if c_eng is not None:
                            tex_out = c_eng.insert_citations(tex_out, style=insert_citations).cited_text
                        out_name = f"Humanized_{fname}"
                        bundle_outputs.append((out_name, tex_out.encode("utf-8")))
                        file_summaries.append(
                            {
                                "File": fname,
                                "Format": "LaTeX (.tex)",
                                "Details": "Math & preamble zones protected; prose humanized in-place",
                                "Transformations": mod.get_telemetry_summary()["Total Transformations"],
                            }
                        )
                        preview_diffs.append((fname, tex_in, tex_out))

                    elif ext in (".txt", ".md"):
                        txt_in = raw_bytes.decode("utf-8", errors="replace")
                        txt_out = mod.modify_text(txt_in, citation_engine=c_eng)
                        out_name = f"Humanized_{fname}"
                        bundle_outputs.append((out_name, txt_out.encode("utf-8")))
                        file_summaries.append(
                            {
                                "File": fname,
                                "Format": f"Text ({ext})",
                                "Details": "Processed in-memory",
                                "Transformations": mod.get_telemetry_summary()["Total Transformations"],
                            }
                        )
                        preview_diffs.append((fname, txt_in, txt_out))

                    elif ext == ".zip":
                        code_h = CodeCommentHumanizer(persona="intermediate", intensity=intensity)
                        zip_entries, z_manifest = process_zip_archive_bytes(
                            raw_bytes,
                            text_modifier_fn=lambda t: mod.modify_text(t, citation_engine=c_eng),
                            docx_modifier_fn=lambda t, s=None: mod.modify_line(t, section_name=s or "body"),
                            code_humanizer_fn=lambda c, p: code_h.humanize_code(c, filename=p).humanized_code,
                            latex_processor_fn=lambda t: process_latex_document(t, mod),
                        )
                        for z_rel, z_data in zip_entries:
                            bundle_outputs.append((z_rel, z_data))
                        file_summaries.append(
                            {
                                "File": fname,
                                "Format": "ZIP Archive",
                                "Details": f"Processed {len(z_manifest)} nested files preserving folder hierarchy",
                                "Transformations": mod.get_telemetry_summary()["Total Transformations"],
                            }
                        )

                zip_filename, zip_bytes = create_humanized_docs_zip(bundle_outputs)
                st.session_state["doc_batch_results"] = {
                    "zip_filename": zip_filename,
                    "zip_bytes": zip_bytes,
                    "bundle_outputs": bundle_outputs,
                    "summaries": file_summaries,
                    "preview_diffs": preview_diffs,
                }

        batch_res = st.session_state.get("doc_batch_results")
        if batch_res:
            st.success(f"Processed {len(batch_res['summaries'])} upload(s) in-memory with zero data retention.")
            st.dataframe(batch_res["summaries"], use_container_width=True, hide_index=True)

            st.download_button(
                label=f"📦 Download Branded Bundle ({batch_res['zip_filename']})",
                data=batch_res["zip_bytes"],
                file_name=batch_res["zip_filename"],
                mime="application/zip",
                type="primary",
                use_container_width=True,
            )

            if len(batch_res["bundle_outputs"]) == 1:
                single_name, single_data = batch_res["bundle_outputs"][0]
                st.download_button(
                    label=f"⬇️ Download {single_name}",
                    data=single_data,
                    file_name=single_name,
                    use_container_width=True,
                )

            for p_name, p_bef, p_aft in batch_res.get("preview_diffs", [])[:3]:
                with st.expander(f"🔍 Visual Diff Preview: {p_name}", expanded=False):
                    st.markdown(render_visual_diff_html(p_bef[:2500], p_aft[:2500]), unsafe_allow_html=True)

    render_footer()
