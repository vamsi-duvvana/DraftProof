"""Unit tests for the 19-stage TextModifier pipeline, LaTeX protection, and Invariant Gates."""

from __future__ import annotations

from draftproof.ai_detector import analyze_ai_signals, compare_documents_winnowing
from draftproof.config import ConfigNamespace
from draftproof.core.invariants import FactInvariantGate, TellInvariantGate
from draftproof.core.modifier import TextModifier
from draftproof.core.parser import process_latex_document


def test_modifier_scrubs_ai_tells_and_preserves_facts_and_latex() -> None:
    cfg = ConfigNamespace({"style_preset": "academic", "intensity": 85})
    cfg.apply_intensity(85)
    mod = TextModifier(config=cfg, seed=42)

    raw = (
        "In conclusion, it is important to delve into the comprehensive tapestry of Crank-Nicolson schemes "
        "for $u_t = \\alpha u_{xx}$ achieving 99.4% accuracy [1, 2] \\cite{crank1947}."
    )
    out = mod.modify_line(raw)

    # Protected LaTeX math, protected terms, numbers, and citations must remain 100% intact
    assert "$u_t = \\alpha u_{xx}$" in out
    assert "Crank-Nicolson" in out
    assert "99.4%" in out
    assert "[1, 2]" in out
    assert "\\cite{crank1947}" in out
    assert "\x00" not in out

    # AI tells must be scrubbed
    assert "delve into" not in out.lower()
    assert "comprehensive tapestry" not in out.lower()

    tell_ok, in_tells, out_tells = TellInvariantGate("academic").verify(raw, out)
    assert tell_ok and out_tells == 0 and in_tells >= 2

    fact_ok, missing = FactInvariantGate.verify(raw, out)
    assert fact_ok, f"Missing facts: {missing}"


def test_modifier_reduces_winnowing_similarity_and_ai_risk() -> None:
    sample = (
        "In conclusion, it is important to delve into the comprehensive tapestry of modern neural networks. "
        "This study plays a pivotal role in illustrating that artificial intelligence stands as a testament "
        "to human innovation. Furthermore, the interplay between stochastic optimization and computational "
        "scalability provides a robust framework for subsequent empirical inquiries."
    )
    cfg = ConfigNamespace({"style_preset": "conversational", "intensity": 85})
    cfg.apply_intensity(85)
    mod = TextModifier(config=cfg, seed=7)
    out = mod.modify_text(sample)

    before_ai = analyze_ai_signals(sample)
    after_ai = analyze_ai_signals(out)
    sim = compare_documents_winnowing(sample, out)

    assert after_ai.overall_ai_probability < before_ai.overall_ai_probability
    assert sim.guaranteed_8word_matches == 0


def test_latex_zone_parser_preserves_equations_and_humanizes_abstract() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\begin{abstract}
In this study, we delve into the comprehensive tapestry of fluid dynamics.
\end{abstract}
\begin{equation}
E = mc^2 + \int_0^\infty f(x)\,dx
\end{equation}
\section{Methodology}
Previous studies have shown that this method plays a pivotal role in accuracy.
\end{document}"""
    cfg = ConfigNamespace({"style_preset": "academic", "intensity": 80})
    cfg.apply_intensity(80)
    mod = TextModifier(config=cfg, seed=42)
    out_tex = process_latex_document(tex, mod)

    assert r"E = mc^2 + \int_0^\infty f(x)\,dx" in out_tex
    assert "delve into" not in out_tex.lower()
    assert "plays a pivotal role" not in out_tex.lower()
