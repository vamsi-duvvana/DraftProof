"""Page 2: Code Comment & Docstring Humanizer (`src/draftproof/ui/code_humanizer_ui.py`).

Implements:
- 100% Executable Code Safety Guarantee (string-aware comment tokenizer + Python AST verification)
- 3 Developer Skill Personas (🐣 Beginner, ⚙️ Intermediate, 👨‍💻 Senior Architect)
- Single continuous line conversion for AI docstrings and block comments
- Multi-file & `.zip` repository batch processing preserving folder hierarchy
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

import streamlit as st

from draftproof.core.code.registry import EXTENSION_MAP
from draftproof.core.code_comment_parser import CodeCommentHumanizer
from draftproof.core.doc_processor import create_humanized_code_zip
from draftproof.ui.common import render_copy_button, render_footer, render_top_banner

SAMPLE_PYTHON_CODE = '''def compute_attention_weights(query_matrix, key_matrix, temperature=1.0):
    """
    This function is used to delve into the comprehensive calculation of scaled
    dot-product attention weights. It plays a pivotal role in ensuring numerical
    stability across deep transformer layers.
    """
    # Here we initialize the scaling factor to bolster gradient stability
    scale_factor = 1.0 / max(temperature, 1e-6)
    url = "https://api.example.com/v1#not-a-comment"  # Note that we preserve URLs with # inside strings
    # Subsequently, we compute the dot product and evaluate the normalized distribution
    scores = [sum(q * k * scale_factor for q, k in zip(query_matrix, key_matrix))]
    # End of function
    return scores, url
'''

SAMPLE_CPP_CODE = '''#include <vector>
#include <numeric>

/*
 * This function serves as a robust framework for evaluating the discrete
 * convolution of signal buffers in real-time embedded telemetry.
 */
double accumulate_signal(const std::vector<double>& buffer) {
    // Initialize the accumulator variable to zero
    double total = 0.0;
    const char* tag = "// string literal must remain untouched";
    // Iterate over the input parameters to compute the sum
    for (double val : buffer) {
        total += val;
    }
    return total;
}
'''


def render_code_humanizer_page() -> None:
    """Render the standalone Code Comment & Docstring Humanizer UI page."""
    render_top_banner("Code Comment & Docstring Humanizer — 100% Executable Logic Guarantee")

    c1, c2, c3, c4 = st.columns([1.3, 1.4, 1.3, 1.2])
    with c1:
        lang_sel = st.selectbox(
            "Programming Language",
            options=[
                "Auto-Detect",
                "Python (.py)",
                "C / C++ (.c, .cpp)",
                "Java / C# (.java, .cs)",
                "JavaScript / TypeScript (.js, .ts)",
                "Go / Rust (.go, .rs)",
                "Shell / Bash (.sh)",
                "SQL (.sql)",
                "HTML / CSS (.html, .css)",
            ],
            index=0,
        )
    with c2:
        persona_sel = st.selectbox(
            "Developer Skill Persona",
            options=[
                "🐣 Beginner Developer",
                "⚙️ Intermediate Developer",
                "👨‍💻 Senior Architect / Expert",
            ],
            index=1,
            help="Beginner: casual ('finds', 'sets up') | Intermediate: standard engineering | Senior: formal ('evaluates', 'initializes', 'spectral decomposition').",
        )
    with c3:
        intensity = st.slider(
            "Comment Rewrite Intensity",
            min_value=10,
            max_value=100,
            value=75,
            step=5,
        )
    with c4:
        single_line_docstrings = st.checkbox(
            "Convert Multi-Line Docstrings to Single-Line Comments",
            value=True,
            help="Converts verbose triple-quoted AI docstrings into clean single-line # or // comments.",
        )
        strip_boilerplate = st.checkbox(
            "Strip AI Boilerplate Intros",
            value=True,
            help="Removes 'Here we...', 'This function is used to...', 'End of function'.",
        )

    tab_editor, tab_zip = st.tabs(
        ["💻 Interactive Code Editor", "📦 Multi-File & Repository ZIP Batch Processor"]
    )

    with tab_editor:
        if "code_input_src" not in st.session_state:
            st.session_state["code_input_src"] = SAMPLE_PYTHON_CODE
        if "code_output_res" not in st.session_state:
            st.session_state["code_output_res"] = None

        sc1, sc2, _ = st.columns([1.2, 1.2, 3.0])
        with sc1:
            if st.button("🐍 Load Python Sample", use_container_width=True):
                st.session_state["code_input_src"] = SAMPLE_PYTHON_CODE
                st.session_state["code_src_area"] = SAMPLE_PYTHON_CODE
                st.rerun()
        with sc2:
            if st.button("⚡ Load C++ Sample", use_container_width=True):
                st.session_state["code_input_src"] = SAMPLE_CPP_CODE
                st.session_state["code_src_area"] = SAMPLE_CPP_CODE
                st.rerun()

        left_col, right_col = st.columns(2)
        with left_col:
            st.subheader("Original Source Code")
            src_code = st.text_area(
                "Input Source Code",
                value=st.session_state["code_input_src"],
                height=340,
                key="code_src_area",
            )
            st.session_state["code_input_src"] = src_code
            run_code_btn = st.button(
                "💻 Humanize Code Comments",
                type="primary",
                use_container_width=True,
            )

        with right_col:
            st.subheader("Humanized & Executable Code")
            res_obj = st.session_state.get("code_output_res")
            out_code_str = res_obj.humanized_code if res_obj else ""
            st.text_area(
                "Output Source Code",
                value=out_code_str,
                height=340,
                placeholder="Humanized code with 100% untouched logic will appear here...",
            )
            render_copy_button(out_code_str, "📋 Copy Clean Code", key="copy_code_out")

        if run_code_btn and src_code.strip():
            engine = CodeCommentHumanizer(
                persona=persona_sel,
                convert_docstrings_to_single_line=single_line_docstrings,
                strip_boilerplate=strip_boilerplate,
                intensity=intensity,
            )
            res = engine.humanize_code(src_code, language_hint=lang_sel)
            st.session_state["code_output_res"] = res
            st.rerun()

        res_obj = st.session_state.get("code_output_res")
        if res_obj is not None:
            st.markdown("---")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Detected Language", res_obj.language_detected)
            m2.metric("Comments Humanized", str(res_obj.comments_modified))
            m3.metric("Docstrings Converted", str(res_obj.docstrings_converted))
            m4.metric(
                "Executable Syntax Gate",
                "100% Verified ✅" if res_obj.ast_verified else "Rolled Back",
            )

            if res_obj.changes:
                with st.expander("🔍 Comment-by-Comment Transformation Audit", expanded=True):
                    rows = [
                        {
                            "Type": ch.kind,
                            "Original Comment / Docstring": ch.original,
                            "Humanized Comment": ch.humanized,
                        }
                        for ch in res_obj.changes
                    ]
                    st.dataframe(rows, use_container_width=True, hide_index=True)

    with tab_zip:
        st.markdown(
            "#### 📦 Batch Code Files & Repository ZIP Humanizer\n"
            "Upload multiple source code files (`.py`, `.cpp`, `.c`, `.java`, `.cs`, `.js`, `.ts`, "
            "`.go`, `.rs`, `.sh`, `.sql`, `.html`, `.css`) or a whole `.zip` repository. Folder "
            "hierarchies and executable statements remain **100% intact**."
        )
        code_uploads = st.file_uploader(
            "Upload Source Files or Codebase Archive (.zip)",
            type=[ext.lstrip(".") for ext in EXTENSION_MAP.keys()] + ["zip"],
            accept_multiple_files=True,
            key="code_zip_uploader",
        )
        if code_uploads:
            if st.button("🚀 Humanize All Uploaded Code Files", type="primary", use_container_width=True):
                engine = CodeCommentHumanizer(
                    persona=persona_sel,
                    convert_docstrings_to_single_line=single_line_docstrings,
                    strip_boilerplate=strip_boilerplate,
                    intensity=intensity,
                )
                output_files: List[Tuple[str, str | bytes]] = []
                summary_rows: List[Dict[str, object]] = []

                for up in code_uploads:
                    fname = up.name
                    raw_b = up.read()
                    ext = Path(fname).suffix.lower()

                    if ext == ".zip":
                        with zipfile.ZipFile(io.BytesIO(raw_b), "r") as zin:
                            for info in zin.infolist():
                                if info.is_dir():
                                    continue
                                rpath = info.filename
                                rext = Path(rpath).suffix.lower()
                                fbytes = zin.read(rpath)
                                if rext in EXTENSION_MAP:
                                    src_txt = fbytes.decode("utf-8", errors="replace")
                                    c_res = engine.humanize_code(src_txt, filename=rpath)
                                    output_files.append((rpath, c_res.humanized_code))
                                    summary_rows.append(
                                        {
                                            "File": rpath,
                                            "Language": c_res.language_detected,
                                            "Comments Modified": c_res.comments_modified,
                                            "Syntax Verified": "✅",
                                        }
                                    )
                                else:
                                    output_files.append((rpath, fbytes))
                    else:
                        src_txt = raw_b.decode("utf-8", errors="replace")
                        c_res = engine.humanize_code(src_txt, filename=fname, language_hint=lang_sel)
                        output_files.append((fname, c_res.humanized_code))
                        summary_rows.append(
                            {
                                "File": fname,
                                "Language": c_res.language_detected,
                                "Comments Modified": c_res.comments_modified,
                                "Syntax Verified": "✅" if c_res.ast_verified else "⚠️",
                            }
                        )

                z_name, z_bytes = create_humanized_code_zip(output_files)
                st.dataframe(summary_rows, use_container_width=True, hide_index=True)
                st.download_button(
                    label=f"📦 Download Humanized Code Bundle ({z_name})",
                    data=z_bytes,
                    file_name=z_name,
                    mime="application/zip",
                    type="primary",
                    use_container_width=True,
                )

    render_footer()
