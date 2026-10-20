"""Language Extension & Syntax Auto-Detector Registry (`src/draftproof/core/code/registry.py`)."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from draftproof.core.code.base import LanguageSyntaxSpec

LANGUAGE_SPECS: Dict[str, LanguageSyntaxSpec] = {
    "python": LanguageSyntaxSpec(
        name="Python",
        single_line_markers=("#",),
        block_comment_delims=(),
        supports_triple_quotes=True,
        supports_python_docstrings=True,
    ),
    "c_family": LanguageSyntaxSpec(
        name="C / C++ / Java / C# / JS / TS / Go / Rust",
        single_line_markers=("//",),
        block_comment_delims=(("/*", "*/"),),
        supports_backtick_strings=True,
    ),
    "shell": LanguageSyntaxSpec(
        name="Shell / Bash",
        single_line_markers=("#",),
        block_comment_delims=(),
    ),
    "sql": LanguageSyntaxSpec(
        name="SQL",
        single_line_markers=("--",),
        block_comment_delims=(("/*", "*/"),),
    ),
    "html_css": LanguageSyntaxSpec(
        name="HTML / CSS",
        single_line_markers=(),
        block_comment_delims=(("<!--", "-->"), ("/*", "*/")),
    ),
}

EXTENSION_MAP: Dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".c": "c_family",
    ".cpp": "c_family",
    ".cc": "c_family",
    ".h": "c_family",
    ".hpp": "c_family",
    ".java": "c_family",
    ".cs": "c_family",
    ".js": "c_family",
    ".jsx": "c_family",
    ".ts": "c_family",
    ".tsx": "c_family",
    ".go": "c_family",
    ".rs": "c_family",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".sql": "sql",
    ".html": "html_css",
    ".htm": "html_css",
    ".css": "html_css",
}


def detect_language_spec(source: str = "", filename: str = "", language_hint: str = "Auto-Detect") -> LanguageSyntaxSpec:
    """Resolve `LanguageSyntaxSpec` from explicit hint, file extension, or content heuristics."""
    hint = (language_hint or "").strip().lower()
    if "python" in hint or hint == "py":
        return LANGUAGE_SPECS["python"]
    if any(k in hint for k in ("c++", "java", "c#", "javascript", "typescript", "go", "rust", "c_family")):
        return LANGUAGE_SPECS["c_family"]
    if "shell" in hint or "bash" in hint:
        return LANGUAGE_SPECS["shell"]
    if "sql" in hint:
        return LANGUAGE_SPECS["sql"]
    if "html" in hint or "css" in hint:
        return LANGUAGE_SPECS["html_css"]

    if filename:
        ext = Path(filename).suffix.lower()
        if ext in EXTENSION_MAP:
            return LANGUAGE_SPECS[EXTENSION_MAP[ext]]

    # Content-based auto-detection
    if "def " in source or "import " in source or '"""' in source:
        return LANGUAGE_SPECS["python"]
    if "SELECT " in source.upper() or "--" in source:
        return LANGUAGE_SPECS["sql"]
    if "<!--" in source:
        return LANGUAGE_SPECS["html_css"]
    if "//" in source or "/*" in source or "function " in source or "#include" in source:
        return LANGUAGE_SPECS["c_family"]
    return LANGUAGE_SPECS["python"]
