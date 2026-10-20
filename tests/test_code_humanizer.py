"""Unit tests for String-Aware Code Comment & Docstring Humanizer and AST safety."""

from __future__ import annotations

import ast

from draftproof.core.code_comment_parser import CodeCommentHumanizer


def test_python_string_aware_comment_humanizer_and_ast_safety() -> None:
    py_src = '''def process_items(items):
    """
    This function is used to delve into the comprehensive evaluation
    of input parameters.
    """
    # Here we initialize the output list and iterate over the parameters
    tag = "https://example.com/#not-a-comment"
    hash_literal = "# this string literal must never be modified: delve into"
    result = [x * 2 for x in items]  # Computes the doubled values
    return result, tag, hash_literal
'''
    for persona in ("beginner", "intermediate", "senior"):
        engine = CodeCommentHumanizer(
            persona=persona,
            convert_docstrings_to_single_line=True,
            strip_boilerplate=True,
            intensity=85,
        )
        res = engine.humanize_code(py_src, filename="sample.py")
        assert res.ast_verified is True
        # Must compile and execute identically!
        ast.parse(res.humanized_code)
        ns_orig: dict = {}
        ns_new: dict = {}
        exec(py_src, ns_orig)
        exec(res.humanized_code, ns_new)
        assert ns_orig["process_items"]([1, 2, 3]) == ns_new["process_items"]([1, 2, 3])
        # String literals with # must be 100% untouched
        assert '"# this string literal must never be modified: delve into"' in res.humanized_code
        assert '"https://example.com/#not-a-comment"' in res.humanized_code
        # Multi-line docstring converted to single-line # comment
        assert '"""' not in res.humanized_code


def test_c_family_and_sql_comment_humanizer() -> None:
    cpp_src = """int main() {
    const char* s = "// inside string delve into";
    // Initialize the counter and evaluate the parameters
    return 0;
}
"""
    eng = CodeCommentHumanizer(persona="beginner", intensity=85)
    res = eng.humanize_code(cpp_src, filename="main.cpp")
    assert '"// inside string delve into"' in res.humanized_code
    assert "set up" in res.humanized_code.lower() or "check" in res.humanized_code.lower()
