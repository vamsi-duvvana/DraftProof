"""Automated Streamlit AppTest suite verifying all navigation pages and traffic offload card."""

from __future__ import annotations

from pathlib import Path
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


def test_streamlit_offload_card_query_param() -> None:
    """Verify `?test_card=1` renders the High-Demand traffic offload card without exception (`AGENTS.md`)."""
    at = AppTest.from_file(APP_PATH)
    at.query_params["test_card"] = "1"
    at.run(timeout=15)
    assert not at.exception


def test_streamlit_all_pages_render_and_execute() -> None:
    """Verify main app and all 6 navigation pages load and execute interactive workflows cleanly."""
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=15)
    assert not at.exception

    # 1. Humanizer page: load Academic Abstract sample and click Humanize Text
    sample_btn = [b for b in at.button if "Academic Abstract" in b.label][0]
    sample_btn.click().run(timeout=15)
    assert not at.exception
    humanize_btn = [b for b in at.button if "Humanize Text" in b.label][0]
    humanize_btn.click().run(timeout=15)
    assert not at.exception
    assert st_session_state_value_check(at)

    # 2. Code Comment Humanizer page: click Humanize Code Comments
    at.button(key="nav_code_humanizer").click().run(timeout=15)
    assert not at.exception
    code_btn = [b for b in at.button if "Humanize Code Comments" in b.label][0]
    code_btn.click().run(timeout=15)
    assert not at.exception
    assert at.session_state["code_output_res"] is not None

    # 3. Citation Inserter page: click Insert Contextual Citations
    at.button(key="nav_citation").click().run(timeout=15)
    assert not at.exception
    cite_btn = [b for b in at.button if "Insert Contextual Citations" in b.label][0]
    cite_btn.click().run(timeout=15)
    assert not at.exception
    assert at.session_state["citation_last_result"] is not None

    # 4. Pairwise Similarity & AI Checker page: click Auto-Humanize & Fix All Flagged Tells
    at.button(key="nav_checker").click().run(timeout=15)
    assert not at.exception
    fix_btn = [b for b in at.button if "Auto-Humanize" in b.label][0]
    fix_btn.click().run(timeout=15)
    assert not at.exception

    # 5. Voice Matcher & Watermark Lab page: click Extract & Activate My Voice Profile
    at.button(key="nav_voice_watermark").click().run(timeout=15)
    assert not at.exception
    vp_btn = [b for b in at.button if "Extract & Activate My Voice Profile" in b.label][0]
    vp_btn.click().run(timeout=15)
    assert not at.exception
    assert at.session_state["active_voice_profile"] is not None

    # 6. Feedback & Taxonomy Builder page: click Generate Issue & Submission Package
    at.button(key="nav_feedback").click().run(timeout=15)
    assert not at.exception
    fb_btn = [b for b in at.button if "Generate Issue" in b.label][0]
    fb_btn.click().run(timeout=15)
    assert not at.exception
    assert at.session_state["generated_feedback"] is not None


def st_session_state_value_check(at: AppTest) -> bool:
    return bool(at.session_state["humanizer_output_text"]) and (
        at.session_state["humanizer_last_telemetry"] is not None
    )
