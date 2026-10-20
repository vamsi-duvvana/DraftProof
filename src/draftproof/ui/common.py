"""Shared UI Styling, Traffic Offload Guard, Visual Diff Renderer & Footer (`common.py`)."""

from __future__ import annotations

import difflib
import html
import json
import random
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from draftproof.config import load_raw_global_config


def inject_global_css() -> None:
    """Inject DraftProof dark crimson/charcoal styling matching the official UI design."""
    st.markdown(
        """
        <style>
        /* Main background & typography */
        .stApp {
            background-color: #0E1117;
            color: #F0F2F6;
        }
        [data-testid="stSidebar"] {
            background-color: #151821;
            border-right: 1px solid rgba(255, 255, 255, 0.07);
        }
        /* Top DraftProof Crimson Banner */
        .draftproof-banner {
            background: linear-gradient(90deg, #4A0404 0%, #680707 50%, #3A0202 100%);
            border: 1px solid rgba(230, 57, 70, 0.45);
            border-radius: 10px;
            padding: 16px 24px;
            margin-bottom: 18px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45);
        }
        .draftproof-brand {
            font-size: 24px;
            font-weight: 900;
            letter-spacing: 1.5px;
            color: #FFFFFF;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }
        .draftproof-brand span {
            color: #FF3B3B;
        }
        .draftproof-subtitle {
            color: #E0B4B4;
            font-style: italic;
            font-size: 14.5px;
            margin-left: 16px;
        }
        .draftproof-version-pill {
            background: rgba(230, 57, 70, 0.25);
            border: 1px solid #E63946;
            color: #FFD6D6;
            padding: 4px 12px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.6px;
        }
        /* Metric & telemetry cards */
        .telemetry-card {
            background: #181C26;
            border: 1px solid rgba(255, 255, 255, 0.09);
            border-radius: 10px;
            padding: 14px 16px;
            margin-bottom: 10px;
        }
        .telemetry-label {
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: #9DA5B4;
            margin-bottom: 4px;
        }
        .telemetry-value {
            font-size: 22px;
            font-weight: 800;
            color: #FFFFFF;
        }
        /* Diff highlighting */
        .diff-box {
            background: #141720;
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 8px;
            padding: 16px;
            line-height: 1.75;
            font-size: 15px;
            color: #E5E9F0;
        }
        .diff-del {
            background: rgba(230, 57, 70, 0.22);
            color: #FF858D;
            text-decoration: line-through;
            padding: 1px 5px;
            border-radius: 4px;
            margin: 0 2px;
        }
        .diff-ins {
            background: rgba(46, 204, 113, 0.22);
            color: #69F0AE;
            font-weight: 600;
            padding: 1px 5px;
            border-radius: 4px;
            margin: 0 2px;
        }
        /* Sentence risk heatmap */
        .risk-high {
            background: rgba(230, 57, 70, 0.24);
            border-left: 3px solid #E63946;
            padding: 6px 10px;
            border-radius: 4px;
            margin-bottom: 6px;
        }
        .risk-moderate {
            background: rgba(244, 162, 97, 0.20);
            border-left: 3px solid #F4A261;
            padding: 6px 10px;
            border-radius: 4px;
            margin-bottom: 6px;
        }
        .risk-low {
            background: rgba(42, 157, 143, 0.18);
            border-left: 3px solid #2A9D8F;
            padding: 6px 10px;
            border-radius: 4px;
            margin-bottom: 6px;
        }
        .counter-caption {
            font-size: 12.5px;
            color: #9DA5B4;
            margin-top: -6px;
            margin-bottom: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_traffic_offload_guard() -> None:
    """High-Demand Traffic Offloading Guard (`AGENTS.md` Section 3B & 4.3).

    Supports `?test_card=1` developer preview and `traffic_balancing.enable_offload`.
    """
    qp = st.query_params
    force_test_card = str(qp.get("test_card", "0")) == "1"

    cfg = load_raw_global_config()
    tb = cfg.get("traffic_balancing", {})
    enable_offload = bool(tb.get("enable_offload", False))
    offload_pct = int(tb.get("offload_percentage", 85))
    worker_nodes = tb.get(
        "worker_nodes",
        [
            "https://draftproof1.streamlit.app/",
            "https://draftproof2.streamlit.app/",
            "https://draftproof3.streamlit.app/",
            "https://draftproof4.streamlit.app/",
            "https://draftproof5.streamlit.app/",
            "https://draftproof6.streamlit.app/",
        ],
    )

    should_offload = force_test_card or (
        enable_offload
        and not st.session_state.get("authenticated", False)
        and random.randint(1, 100) <= offload_pct
    )

    if should_offload:
        chosen_mirror = random.choice(worker_nodes) if worker_nodes else "https://draftproof1.streamlit.app/"
        st.markdown(
            f"""
            <div style="background:#181B24;border:1px solid #E63946;border-radius:12px;padding:28px;max-width:680px;margin:40px auto;text-align:center;">
                <h2 style="color:#FF4D4D;margin-top:0;">⚡ High-Demand Cluster Routing Active</h2>
                <p style="color:#D8DEE9;font-size:16px;line-height:1.6;">
                    To guarantee instant zero-latency processing and prevent CPU throttling, your session
                    has been assigned to a dedicated high-speed DraftProof Worker Mirror.
                </p>
                <div style="margin:24px 0;">
                    <a href="{chosen_mirror}" target="_blank" style="background:#E63946;color:#FFFFFF;padding:12px 28px;border-radius:8px;font-weight:700;text-decoration:none;font-size:16px;">
                        Launch Dedicated Fast Mirror →
                    </a>
                </div>
                <p style="font-size:13px;color:#8892B0;">
                    All 6 worker nodes run the exact v2.0.0 Zero-AI Engine with 100% in-memory privacy.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.stop()


def render_top_banner(subtitle: str = "Intelligent Similarity Evasion & Multi-Algorithm Checker") -> None:
    """Render the signature dark-crimson DRAFTPROOF header banner."""
    st.markdown(
        f"""
        <div class="draftproof-banner">
            <div>
                <span class="draftproof-brand">DRAFT<span>PROOF</span></span>
                <span class="draftproof-subtitle">{html.escape(subtitle)}</span>
            </div>
            <span class="draftproof-version-pill">ENGINE v2.0.0 • 100% ZERO-AI</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_visual_diff_html(before_text: str, after_text: str) -> str:
    """Generate word-level HTML visual diff highlighting removed AI phrases and new replacements."""
    before_words = (before_text or "").split()
    after_words = (after_text or "").split()
    matcher = difflib.SequenceMatcher(None, before_words, after_words, autojunk=False)

    parts: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            parts.append(html.escape(" ".join(before_words[i1:i2])))
        elif tag == "delete":
            deleted = html.escape(" ".join(before_words[i1:i2]))
            parts.append(f'<span class="diff-del">{deleted}</span>')
        elif tag == "insert":
            inserted = html.escape(" ".join(after_words[j1:j2]))
            parts.append(f'<span class="diff-ins">{inserted}</span>')
        elif tag == "replace":
            deleted = html.escape(" ".join(before_words[i1:i2]))
            inserted = html.escape(" ".join(after_words[j1:j2]))
            parts.append(
                f'<span class="diff-del">{deleted}</span><span class="diff-ins">{inserted}</span>'
            )

    body = " ".join(parts)
    return f'<div class="diff-box">{body}</div>'


def render_copy_button(text_to_copy: str, button_label: str = "📋 Copy to Clipboard", key: str = "copy_btn") -> None:
    """Render a 1-click browser-native clipboard copy button."""
    if not text_to_copy:
        return
    escaped_json = json.dumps(text_to_copy)
    safe_id = f"btn_{abs(hash(key)) % 1000000}"
    components.html(
        f"""
        <div style="display:flex;justify-content:flex-end;margin:0;padding:0;">
            <button id="{safe_id}" style="
                background:#232836;
                color:#ECEFF4;
                border:1px solid rgba(255,255,255,0.18);
                border-radius:6px;
                padding:5px 12px;
                font-size:12.5px;
                font-family:sans-serif;
                cursor:pointer;
                font-weight:600;
            ">{html.escape(button_label)}</button>
        </div>
        <script>
        const btn = document.getElementById("{safe_id}");
        if (btn) {{
            btn.addEventListener("click", () => {{
                navigator.clipboard.writeText({escaped_json}).then(() => {{
                    const prev = btn.innerText;
                    btn.innerText = "✅ Copied!";
                    btn.style.borderColor = "#2ECC71";
                    btn.style.color = "#2ECC71";
                    setTimeout(() => {{
                        btn.innerText = prev;
                        btn.style.borderColor = "rgba(255,255,255,0.18)";
                        btn.style.color = "#ECEFF4";
                    }}, 1800);
                }});
            }});
        }}
        </script>
        """,
        height=36,
    )


def render_footer() -> None:
    """Render the standard DraftProof application footer with external verification guide."""
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align:center;padding:12px 18px;background:#141722;border:1px solid rgba(230,57,70,0.3);border-radius:10px;margin-top:10px;">
            <p style="margin:0 0 6px 0;font-size:14.5px;color:#ECEFF4;">
                🔍 <strong>Verify AI Content:</strong> Paste your paragraph
                <a href="https://quillbot.com/ai-content-detector" target="_blank" rel="noopener noreferrer" style="color:#FF6B6B;font-weight:700;text-decoration:underline;">
                    here on QuillBot AI Content Detector
                </a>
                to check the AI content of it.
            </p>
            <p style="margin:0;font-size:12.5px;color:#8892B0;">
                🔒 <strong>100% Local In-Memory Privacy Guarantee</strong> • Zero Generative AI • Deterministic Engine
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
