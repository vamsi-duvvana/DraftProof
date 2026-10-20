"""Page 5: Empirical Voice Matcher & Watermark Forensics Lab (`voice_watermark_ui.py`).

Implements the v2.0.0 flagship features:
1. Empirical Voice Matching Engine: Analyzes user writing samples (.txt, .md, .tex, .docx)
   to mirror authentic sentence variance, contraction rates, and punctuation rhythm.
2. 2026 Watermark & Threat Erasure Lab: Forensically inspects and strips zero-width Unicode
   (U+200B, U+200C, U+200D, U+2060, U+FEFF), Cyrillic/Latin homoglyphs, SynthID token-chain
   periodicity, and C2PA / DOCX tracking metadata.
"""

from __future__ import annotations

import streamlit as st

from draftproof.core.doc_processor import extract_text_from_docx_bytes
from draftproof.core.voice_matcher import analyze_voice_sample
from draftproof.core.watermark import inspect_and_sanitize_watermarks
from draftproof.ui.common import render_copy_button, render_footer, render_top_banner

SAMPLE_WATERMARK_FORENSICS = (
    "The rapid\u200b evolution of large\u200c language models\u200d has introduced invisible "
    "cryptographic\u2060 watermarks — including zero-width Unicode\ufeff spaces and Cyrillic "
    "homoglyphs (\u0430pple, \u0435ngine) — to comply with EU AI Act Article 50 tracking."
)

SAMPLE_USER_WRITING_VOICE = (
    "When we built our first distributed cache, latency spiked every time a node rejoined the ring. "
    "Why? Because consistent hashing alone doesn't stop a cold replica from flooding the storage backend. "
    "We fixed it with a simple token-bucket admission gate; read throughput stabilized within two minutes, "
    "and tail latency dropped from 420ms to 19ms across all six worker nodes."
)


def render_voice_watermark_page() -> None:
    """Render the Empirical Voice Matcher & 2026 Watermark Forensics Lab page."""
    render_top_banner("Empirical Voice Matching Engine & 2026 Watermark Forensics Lab")

    tab_wm, tab_voice = st.tabs(
        [
            "🚨 2026 Watermark, Zero-Width & SynthID Forensics",
            "🧬 Empirical Voice Matching Engine (Personal Style Calibration)",
        ]
    )

    with tab_wm:
        st.markdown(
            "#### 🔥 2026 Threat Erasure Protocol (SynthID, Claude Watermarks & Zero-Width Unicode)\n"
            "Scan any text or `.docx` file for invisible zero-width Unicode (`U+200B`..`U+2060`), "
            "Cyrillic/Latin homoglyph spoofing, statistical token-list green-bucket clustering, and "
            "typographic em-dashes."
        )
        if "wm_lab_input" not in st.session_state:
            st.session_state["wm_lab_input"] = SAMPLE_WATERMARK_FORENSICS

        if st.button("🔬 Load Watermarked & Homoglyph Test Sample"):
            st.session_state["wm_lab_input"] = SAMPLE_WATERMARK_FORENSICS
            st.session_state["wm_forensics_area"] = SAMPLE_WATERMARK_FORENSICS
            st.rerun()

        wm_input = st.text_area(
            "Input Text for Forensic Watermark Inspection",
            value=st.session_state["wm_lab_input"],
            height=190,
            key="wm_forensics_area",
        )
        st.session_state["wm_lab_input"] = wm_input

        wm_rep = inspect_and_sanitize_watermarks(wm_input)

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Watermark Risk Level", wm_rep.watermark_risk_level)
        m2.metric("Zero-Width Chars Found", str(wm_rep.zero_width_count))
        m3.metric("Homoglyphs Normalized", str(wm_rep.homoglyph_count))
        m4.metric("Em/En-Dashes Found", str(wm_rep.em_dash_count))
        m5.metric("SynthID Green z-Score", f"{wm_rep.synthid_z_score:+.2f}")

        if wm_rep.findings:
            for finding in wm_rep.findings:
                st.warning(f"🚨 {finding}")
        else:
            st.success("✅ Zero hidden Unicode trackers or homoglyph watermarks detected.")

        st.subheader("Sanitized & Scrubbed Output")
        st.text_area(
            "Clean Text (100% Purged of Zero-Width Unicode & Homoglyphs)",
            value=wm_rep.sanitized_text,
            height=160,
        )
        render_copy_button(wm_rep.sanitized_text, "📋 Copy Sanitized Text", key="copy_wm_clean")

    with tab_voice:
        st.markdown(
            "#### 🎙️ Empirical Voice Matching Engine (v2.0.0)\n"
            "Paste a sample of **your own authentic past writing** (or upload a past `.docx` / `.tex` / `.txt` paper). "
            "DraftProof extracts your personal stylometric fingerprint (sentence length variance, burstiness, "
            "contraction frequency, punctuation cadence, and lexical density) and calibrates the Humanizer "
            "pipeline to match **your** natural voice."
        )
        if "voice_sample_text" not in st.session_state:
            st.session_state["voice_sample_text"] = SAMPLE_USER_WRITING_VOICE

        if st.button("📝 Load Sample Author Writing Voice"):
            st.session_state["voice_sample_text"] = SAMPLE_USER_WRITING_VOICE
            st.session_state["voice_sample_area"] = SAMPLE_USER_WRITING_VOICE
            st.rerun()

        voice_txt = st.text_area(
            "Your Reference Writing Sample",
            value=st.session_state["voice_sample_text"],
            height=190,
            key="voice_sample_area",
        )
        st.session_state["voice_sample_text"] = voice_txt

        up_voice_file = st.file_uploader(
            "Or Upload Past Writing Sample (.docx, .txt, .md, .tex)",
            type=["docx", "txt", "md", "tex"],
            key="voice_file_upload",
        )
        if up_voice_file is not None:
            raw_b = up_voice_file.read()
            if up_voice_file.name.lower().endswith(".docx"):
                voice_txt = extract_text_from_docx_bytes(raw_b)
            else:
                voice_txt = raw_b.decode("utf-8", errors="replace")

        if st.button("🧬 Extract & Activate My Voice Profile", type="primary", use_container_width=True):
            profile = analyze_voice_sample(voice_txt)
            st.session_state["active_voice_profile"] = profile
            st.success(
                "✅ Empirical Voice Profile extracted and activated! It will now automatically calibrate the Plagiarism & AI Remover."
            )

        active_vp = st.session_state.get("active_voice_profile") or analyze_voice_sample(voice_txt)
        if active_vp:
            v1, v2, v3, v4, v5 = st.columns(5)
            v1.metric("Mean Sentence Length", f"{active_vp.mean_sentence_length} words")
            v2.metric("Sentence Std Dev", f"±{active_vp.sentence_length_std} words")
            v3.metric("Burstiness Index", f"{active_vp.burstiness_index}")
            v4.metric("Type-Token Ratio", f"{active_vp.type_token_ratio}")
            v5.metric("Recommended Preset", active_vp.recommended_preset.title())

            with st.expander("📋 Full Stylometric Voice Calibration Parameters", expanded=True):
                st.json(active_vp.to_dict())

    render_footer()
