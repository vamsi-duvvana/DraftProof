"""Unit tests for Watermark Forensics, Voice Matcher, VIP Whitelist, and Winnowing Similarity."""

from __future__ import annotations

from draftproof.ai_detector import (
    analyze_ai_signals,
    compare_documents_winnowing,
    compression_perplexity,
)
from draftproof.core.voice_matcher import analyze_voice_sample
from draftproof.core.watermark import inspect_and_sanitize_watermarks
from draftproof.github_verifier import is_whitelisted_user


def test_watermark_zero_width_and_homoglyph_sanitization() -> None:
    dirty = "Hello\u200b world\u200c with\u200d hidden\u2060 trackers\ufeff and \u0430pple — test."
    rep = inspect_and_sanitize_watermarks(dirty)
    assert rep.zero_width_count == 5
    assert rep.homoglyph_count == 1
    assert rep.em_dash_count == 1
    assert "\u200b" not in rep.sanitized_text
    assert "apple" in rep.sanitized_text
    assert rep.watermark_risk_level == "High"


def test_winnowing_8_word_guarantee_and_perplexity() -> None:
    doc_a = "We analyze the parabolic heat equation using the implicit Crank-Nicolson finite difference scheme."
    doc_b = "We analyze the parabolic heat equation using the implicit Crank-Nicolson finite difference scheme."
    sim_identical = compare_documents_winnowing(doc_a, doc_b)
    assert sim_identical.winnowing_fingerprint_similarity_pct == 100.0
    assert sim_identical.guaranteed_8word_matches >= 1

    perp = compression_perplexity(doc_a)
    assert 5.0 <= perp <= 100.0

    ai_rep = analyze_ai_signals(
        "In conclusion, it is important to delve into the comprehensive tapestry of neural networks."
    )
    assert len(ai_rep.detected_tells) >= 2


def test_voice_matcher_and_vip_whitelist() -> None:
    sample = (
        "First, we tested the cluster under synthetic load. It held up well. "
        "However, when a single storage node dropped connections, tail latency spiked across all workers."
    )
    vp = analyze_voice_sample(sample)
    assert vp.sample_word_count > 15
    assert vp.sentence_count == 3
    assert vp.burstiness_index > 0

    assert is_whitelisted_user("octocat")
    assert is_whitelisted_user("OctoCat")
    assert is_whitelisted_user("https://github.com/octocat")
    assert not is_whitelisted_user("random_unlisted_user_99999")
