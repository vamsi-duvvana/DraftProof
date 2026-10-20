"""Unit tests for the decoupled CitationEngine and BibTeX/LaTeX/JSON reference generators."""

from __future__ import annotations

import json

from draftproof.core.citation_engine import CitationEngine


def test_citation_engine_auto_and_exact_counts() -> None:
    engine = CitationEngine(seed=42)
    text = (
        "Deep neural networks optimize non-convex loss landscapes using stochastic gradient descent. "
        "Self-attention layers model token dependencies across long context windows. "
        "Regularization techniques prevent overfitting in overparameterized transformer architectures."
    )
    res_auto = engine.insert_citations(text, style="IEEE [1]", count="Auto", discipline="Auto-Detect Field")
    assert res_auto.citations_inserted >= 1
    assert "[1]" in res_auto.cited_text
    assert res_auto.detected_discipline == "Computer Science & AI"
    assert "@article{" in res_auto.bibtex_content
    assert "\\bibitem{" in res_auto.latex_bibitem_content
    parsed_json = json.loads(res_auto.json_content)
    assert len(parsed_json) == res_auto.citations_inserted

    res_exact = engine.insert_citations(text, style="APA (Author, Year)", count=2, discipline="Quantitative Finance & Economics")
    assert res_exact.citations_inserted == 2
    assert res_exact.detected_discipline == "Quantitative Finance & Economics"
    assert "(" in res_exact.cited_text and ")" in res_exact.cited_text


def test_section_aware_citation_shielding() -> None:
    """Abstract and Conclusion sections must be shielded when body sections exist."""
    engine = CitationEngine(seed=42)
    doc = (
        "# Abstract\n"
        "This paper investigates finite difference discretizations of the parabolic heat equation.\n"
        "# Methodology\n"
        "The Crank-Nicolson implicit scheme achieves second-order convergence across uniform grids.\n"
        "# Conclusion\n"
        "Our numerical simulations confirm unconditional stability across all tested time steps."
    )
    res = engine.insert_citations(doc, style="IEEE [1]", count=3, respect_section_shielding=True)
    lines = res.cited_text.splitlines()
    abstract_line = lines[1]
    method_line = lines[3]
    conclusion_line = lines[5]
    assert "[1]" not in abstract_line
    assert "[1]" in method_line
    assert "[1]" not in conclusion_line
