"""Structural LaTeX (`.tex`) and Markdown Zone Parser (`parser.py`).

Divides documents into `SKIP`, `MATH`, and `PROSE` zones while tracking active section
names (`abstract`, `introduction`, `methodology`, `conclusion`, etc.) for section-aware
citation shielding and 100% compilation safety.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class DocumentZone:
    """Single line or block zone classified by the structural parser."""

    idx: int
    zone_type: str  # "SKIP" | "MATH" | "PROSE"
    text: str
    section: str = "body"


SKIP_ENVIRONMENTS = {
    "tabular",
    "tabular*",
    "table",
    "table*",
    "figure",
    "figure*",
    "tikzpicture",
    "lstlisting",
    "minted",
    "verbatim",
    "thebibliography",
    "filecontents",
    "algorithm",
    "algorithmic",
}

MATH_ENVIRONMENTS = {
    "equation",
    "equation*",
    "align",
    "align*",
    "gather",
    "gather*",
    "multline",
    "multline*",
    "eqnarray",
    "eqnarray*",
    "math",
    "displaymath",
}

SKIP_LINE_PREFIXES = (
    "\\documentclass",
    "\\usepackage",
    "\\usetikzlibrary",
    "\\newcommand",
    "\\renewcommand",
    "\\def\\",
    "\\bibliographystyle",
    "\\bibliography",
    "\\addbibresource",
    "\\printbibliography",
    "\\includegraphics",
    "\\centering",
    "\\label{",
    "\\caption{",
    "\\maketitle",
    "\\tableofcontents",
    "\\author{",
    "\\affiliation",
    "\\date{",
    "\\title{",
    "\\hypersetup",
    "\\geometry",
)


def parse_latex_zones(tex_content: str) -> List[Dict[str, object]]:
    """Parse a `.tex` document line-by-line into `SKIP`, `MATH`, and `PROSE` zones."""
    lines = tex_content.splitlines(keepends=True)
    zones: List[Dict[str, object]] = []

    has_begin_doc = "\\begin{document}" in tex_content
    in_document = not has_begin_doc
    current_section = "body"
    env_stack: List[str] = []
    in_display_math_brackets = False
    in_display_math_dollars = False

    for idx, line in enumerate(lines):
        stripped = line.strip()

        if "\\begin{document}" in stripped:
            in_document = True
            zones.append({"idx": idx, "type": "SKIP", "text": line, "section": current_section})
            continue
        if "\\end{document}" in stripped:
            in_document = False
            zones.append({"idx": idx, "type": "SKIP", "text": line, "section": current_section})
            continue

        if not in_document:
            zones.append({"idx": idx, "type": "SKIP", "text": line, "section": "preamble"})
            continue

        # Comments or empty lines
        if not stripped or stripped.startswith("%"):
            zones.append({"idx": idx, "type": "SKIP", "text": line, "section": current_section})
            continue

        # Detect \begin{abstract} / \end{abstract} as PROSE section (v1.5.0 frontmatter fix)
        if stripped.startswith("\\begin{abstract}"):
            current_section = "abstract"
            zones.append({"idx": idx, "type": "SKIP", "text": line, "section": current_section})
            continue
        if stripped.startswith("\\end{abstract}"):
            current_section = "body"
            zones.append({"idx": idx, "type": "SKIP", "text": line, "section": current_section})
            continue

        # Detect section headers
        sec_match = re.match(r"^\\(?:sub)*section\*?\{([^}]+)\}", stripped)
        if sec_match:
            current_section = sec_match.group(1).strip().lower()
            zones.append({"idx": idx, "type": "SKIP", "text": line, "section": current_section})
            continue

        # Check \begin{env} and \end{env}
        begin_m = re.search(r"\\begin\{([^}]+)\}", stripped)
        end_m = re.search(r"\\end\{([^}]+)\}", stripped)

        if begin_m:
            env_name = begin_m.group(1).strip()
            if env_name in SKIP_ENVIRONMENTS or env_name in MATH_ENVIRONMENTS:
                env_stack.append(env_name)
                z_type = "MATH" if env_name in MATH_ENVIRONMENTS else "SKIP"
                zones.append({"idx": idx, "type": z_type, "text": line, "section": current_section})
                if end_m and end_m.group(1).strip() == env_name and env_stack:
                    env_stack.pop()
                continue

        if env_stack:
            active_env = env_stack[-1]
            z_type = "MATH" if active_env in MATH_ENVIRONMENTS else "SKIP"
            zones.append({"idx": idx, "type": z_type, "text": line, "section": current_section})
            if end_m and end_m.group(1).strip() == active_env:
                env_stack.pop()
            continue

        # Check \[ ... \] and $$ ... $$ display math blocks
        if stripped.startswith("\\["):
            in_display_math_brackets = not ("\\]" in stripped)
            zones.append({"idx": idx, "type": "MATH", "text": line, "section": current_section})
            continue
        if in_display_math_brackets:
            if "\\]" in stripped:
                in_display_math_brackets = False
            zones.append({"idx": idx, "type": "MATH", "text": line, "section": current_section})
            continue

        if stripped.startswith("$$"):
            if stripped.count("$$") == 1:
                in_display_math_dollars = not in_display_math_dollars
            zones.append({"idx": idx, "type": "MATH", "text": line, "section": current_section})
            continue
        if in_display_math_dollars:
            if "$$" in stripped:
                in_display_math_dollars = False
            zones.append({"idx": idx, "type": "MATH", "text": line, "section": current_section})
            continue

        # Skip pure command lines
        if stripped.startswith(SKIP_LINE_PREFIXES) or re.match(r"^\\[a-zA-Z]+(\{[^}]*\})?$", stripped):
            zones.append({"idx": idx, "type": "SKIP", "text": line, "section": current_section})
            continue

        zones.append({"idx": idx, "type": "PROSE", "text": line, "section": current_section})

    return zones


def process_latex_document(tex_content: str, modifier: object, verbose: bool = False) -> str:
    """Process a `.tex` document in-place through `modifier` while protecting math & preamble zones."""
    zones = parse_latex_zones(tex_content)
    out_lines: List[str] = []

    for i, zone in enumerate(zones):
        z_type = str(zone["type"])
        raw_line = str(zone["text"])
        sec = str(zone.get("section", "body"))
        if z_type != "PROSE":
            out_lines.append(raw_line)
            continue

        # Separate inline % LaTeX comment from prose
        comment_part = ""
        prose_part = raw_line
        m_comm = re.search(r"(?<!\\)%.*$", raw_line)
        if m_comm:
            prose_part = raw_line[: m_comm.start()]
            comment_part = raw_line[m_comm.start() :]

        trailing_nl = raw_line[len(raw_line.rstrip("\r\n")) :] if not comment_part else ""
        core_prose = prose_part.rstrip("\r\n")

        # Gather prose-only context lines (v1.1.0 Prose-Only Context Filtering)
        next_ctx: Optional[List[str]] = None
        if i + 1 < len(zones) and zones[i + 1]["type"] == "PROSE":
            next_ctx = [str(zones[i + 1]["text"]).strip()]

        modified_core = modifier.modify_line(  # type: ignore[attr-defined]
            core_prose,
            context_lines=next_ctx,
            section_name=sec,
        )
        out_lines.append(modified_core + comment_part + trailing_nl)

    return "".join(out_lines)
