"""In-Place Word (`.docx`) Stream Processor & Stateless In-Memory ZIP Bundler (`doc_processor.py`).

Implements:
- Character-level sequence alignment (`difflib.SequenceMatcher`) across paragraph runs (`w:r`),
  tables, headers, and footers so bold, italic, underline, colors, fonts, and hyperlinks
  remain 100% intact without adjacent words merging (v1.4.0 fix).
- C2PA & core metadata sanitization (`strip_docx_c2pa_and_metadata`).
- Stateless in-memory ZIP bundling (`create_humanized_docs_zip`, `create_citations_zip`,
  `create_checker_reports_zip`, `create_humanized_code_zip`) and `.zip` input extraction.
"""

from __future__ import annotations

import datetime
import difflib
import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import docx

from draftproof.core.code.registry import EXTENSION_MAP
from draftproof.core.watermark import strip_docx_c2pa_and_metadata


@dataclass
class DocxProcessResult:
    """Result of processing a `.docx` file in-place."""

    filename: str
    output_bytes: bytes
    paragraphs_modified: int
    tables_modified: int
    c2pa_stripped: bool
    extracted_before_text: str = ""
    extracted_after_text: str = ""
    metadata_report: Dict[str, Any] = field(default_factory=dict)


def _align_runs_text(runs: List[Any], original_full: str, modified_full: str) -> None:
    """Distribute `modified_full` back across `runs` using character-level SequenceMatcher alignment."""
    if not runs:
        return
    if len(runs) == 1:
        runs[0].text = modified_full
        return

    # Build character-to-run-index ownership array for original_full
    run_lengths = [len(r.text or "") for r in runs]
    if sum(run_lengths) == 0:
        runs[0].text = modified_full
        return

    char_owners: List[int] = []
    for r_idx, r_len in enumerate(run_lengths):
        char_owners.extend([r_idx] * r_len)

    new_run_Buffers: List[List[str]] = [[] for _ in runs]
    matcher = difflib.SequenceMatcher(None, original_full, modified_full, autojunk=False)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        segment = modified_full[j1:j2]
        if not segment:
            continue
        if tag == "equal":
            for offset, ch in enumerate(segment):
                owner = char_owners[min(i1 + offset, len(char_owners) - 1)]
                new_run_Buffers[owner].append(ch)
        elif tag in ("replace", "insert"):
            if i1 < len(char_owners):
                owner = char_owners[i1]
            elif i1 > 0 and (i1 - 1) < len(char_owners):
                owner = char_owners[i1 - 1]
            else:
                owner = len(runs) - 1
            new_run_Buffers[owner].append(segment)

    for r_idx, r in enumerate(runs):
        r.text = "".join(new_run_Buffers[r_idx])


def _process_paragraph_in_place(
    paragraph: Any,
    transform_fn: Callable[[str, str], str],
    section_name: str,
) -> Tuple[bool, str, str]:
    """Process a single `docx.text.paragraph.Paragraph` preserving run-level formatting."""
    runs = list(paragraph.runs)
    full_text = "".join(r.text or "" for r in runs) if runs else (paragraph.text or "")
    if not full_text or not full_text.strip():
        return False, full_text, full_text

    modified_text = transform_fn(full_text, section_name)
    if modified_text == full_text:
        return False, full_text, full_text

    if runs:
        _align_runs_text(runs, full_text, modified_text)
    else:
        paragraph.text = modified_text
    return True, full_text, modified_text


def extract_text_from_docx_bytes(docx_bytes: bytes) -> str:
    """Extract plain text from a `.docx` byte buffer for inspection or checking."""
    doc = docx.Document(io.BytesIO(docx_bytes))
    chunks: List[str] = []
    for para in doc.paragraphs:
        if para.text and para.text.strip():
            chunks.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    if para.text and para.text.strip():
                        chunks.append(para.text)
    return "\n\n".join(chunks)


def process_docx_bytes(
    docx_bytes: bytes,
    transform_fn: Callable[[str, Optional[str]], str],
    filename: str = "document.docx",
    strip_c2pa: bool = True,
) -> DocxProcessResult:
    """Process a `.docx` file in-place across body paragraphs, tables, headers, and footers."""
    doc = docx.Document(io.BytesIO(docx_bytes))
    current_section = "body"
    paragraphs_modified = 0
    tables_modified = 0
    before_chunks: List[str] = []
    after_chunks: List[str] = []

    def _wrapped_transform(text: str, sec: str) -> str:
        try:
            return transform_fn(text, sec)
        except TypeError:
            return transform_fn(text)  # type: ignore[misc,call-arg]

    # 1. Body paragraphs (with Heading style awareness for section shielding)
    for para in doc.paragraphs:
        style_name = (getattr(para.style, "name", "") or "").lower()
        p_text = (para.text or "").strip()
        if "heading" in style_name or "title" in style_name:
            if p_text:
                current_section = p_text.lower()
            before_chunks.append(p_text)
            after_chunks.append(p_text)
            continue
        if p_text.lower() in (
            "abstract",
            "introduction",
            "conclusion",
            "conclusions",
            "references",
            "bibliography",
            "acknowledgments",
            "declarations",
        ):
            current_section = p_text.lower()
            before_chunks.append(p_text)
            after_chunks.append(p_text)
            continue

        changed, bef, aft = _process_paragraph_in_place(para, _wrapped_transform, current_section)
        if bef.strip():
            before_chunks.append(bef)
            after_chunks.append(aft)
        if changed:
            paragraphs_modified += 1

    # 2. Tables
    for table in doc.tables:
        table_changed = False
        visited_cells = set()
        for row in table.rows:
            for cell in row.cells:
                if id(cell._tc) in visited_cells:
                    continue
                visited_cells.add(id(cell._tc))
                for para in cell.paragraphs:
                    if len((para.text or "").strip()) >= 35:
                        changed, _, _ = _process_paragraph_in_place(para, _wrapped_transform, "table")
                        if changed:
                            table_changed = True
        if table_changed:
            tables_modified += 1

    # 3. Headers & Footers (only long prose footnotes/headers >=50 chars)
    for section in doc.sections:
        for hf in (section.header, section.footer):
            if hf is None:
                continue
            for para in hf.paragraphs:
                if len((para.text or "").strip()) >= 50:
                    _process_paragraph_in_place(para, _wrapped_transform, "header_footer")

    meta_report: Dict[str, Any] = {}
    if strip_c2pa:
        meta_report = strip_docx_c2pa_and_metadata(doc)

    out_buf = io.BytesIO()
    doc.save(out_buf)
    return DocxProcessResult(
        filename=filename,
        output_bytes=out_buf.getvalue(),
        paragraphs_modified=paragraphs_modified,
        tables_modified=tables_modified,
        c2pa_stripped=strip_c2pa,
        extracted_before_text="\n\n".join(before_chunks),
        extracted_after_text="\n\n".join(after_chunks),
        metadata_report=meta_report,
    )


def _timestamp_str() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def create_humanized_docs_zip(
    files: List[Tuple[str, bytes | str]], timestamp: Optional[str] = None
) -> Tuple[str, bytes]:
    """Bundle processed documents into a stateless in-memory ZIP archive."""
    ts = timestamp or _timestamp_str()
    zip_name = f"DraftProof_Humanized_Docs_{ts}.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname, payload in files:
            data = payload.encode("utf-8") if isinstance(payload, str) else payload
            zf.writestr(fname, data)
    return zip_name, buf.getvalue()


def create_citations_zip(
    cited_text: str,
    bibtex_str: str,
    latex_str: str,
    json_str: str,
    formatted_bib: str = "",
    docx_item: Optional[Tuple[str, bytes]] = None,
    timestamp: Optional[str] = None,
) -> Tuple[str, bytes]:
    """Bundle cited text/docx and companion `.bib`, `.tex`, and `.json` reference packages into a ZIP."""
    ts = timestamp or _timestamp_str()
    zip_name = f"DraftProof_Citations_{ts}.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("cited_document.txt", cited_text.encode("utf-8"))
        zf.writestr("citations.bib", bibtex_str.encode("utf-8"))
        zf.writestr("citations_thebibliography.tex", latex_str.encode("utf-8"))
        zf.writestr("citations.json", json_str.encode("utf-8"))
        if formatted_bib:
            zf.writestr("formatted_references.md", formatted_bib.encode("utf-8"))
        if docx_item is not None:
            zf.writestr(docx_item[0], docx_item[1])
    return zip_name, buf.getvalue()


def create_checker_reports_zip(
    reports: List[Tuple[str, str | bytes]], timestamp: Optional[str] = None
) -> Tuple[str, bytes]:
    """Bundle similarity & AI detection reports into `DraftProof_Checker_Reports_<TIMESTAMP>.zip`."""
    ts = timestamp or _timestamp_str()
    zip_name = f"DraftProof_Checker_Reports_{ts}.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname, payload in reports:
            data = payload.encode("utf-8") if isinstance(payload, str) else payload
            zf.writestr(fname, data)
    return zip_name, buf.getvalue()


def create_humanized_code_zip(
    code_files: List[Tuple[str, str | bytes]], timestamp: Optional[str] = None
) -> Tuple[str, bytes]:
    """Bundle humanized source code files (preserving directory paths) into a ZIP archive."""
    ts = timestamp or _timestamp_str()
    zip_name = f"DraftProof_Humanized_Code_{ts}.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel_path, payload in code_files:
            data = payload.encode("utf-8") if isinstance(payload, str) else payload
            zf.writestr(rel_path, data)
    return zip_name, buf.getvalue()


def process_zip_archive_bytes(
    zip_bytes: bytes,
    text_modifier_fn: Callable[[str], str],
    docx_modifier_fn: Callable[[str, Optional[str]], str],
    code_humanizer_fn: Optional[Callable[[str, str], str]] = None,
    latex_processor_fn: Optional[Callable[[str], str]] = None,
) -> Tuple[List[Tuple[str, bytes]], List[Dict[str, Any]]]:
    """Extract an uploaded `.zip` in-memory, process all supported files while preserving folder structure."""
    processed_entries: List[Tuple[str, bytes]] = []
    manifest: List[Dict[str, Any]] = []

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zin:
        for info in zin.infolist():
            if info.is_dir():
                continue
            rel_path = info.filename
            if rel_path.startswith("__MACOSX") or Path(rel_path).name.startswith("."):
                continue

            raw_bytes = zin.read(rel_path)
            ext = Path(rel_path).suffix.lower()

            if ext == ".docx":
                res = process_docx_bytes(raw_bytes, docx_modifier_fn, filename=rel_path)
                processed_entries.append((rel_path, res.output_bytes))
                manifest.append(
                    {
                        "file": rel_path,
                        "type": "DOCX",
                        "status": f"Modified {res.paragraphs_modified} paragraphs, C2PA stripped",
                    }
                )
            elif ext == ".tex":
                text_str = raw_bytes.decode("utf-8", errors="replace")
                out_str = (
                    latex_processor_fn(text_str)
                    if latex_processor_fn is not None
                    else text_modifier_fn(text_str)
                )
                processed_entries.append((rel_path, out_str.encode("utf-8")))
                manifest.append({"file": rel_path, "type": "LaTeX", "status": "Processed in-place"})
            elif ext in (".txt", ".md"):
                text_str = raw_bytes.decode("utf-8", errors="replace")
                out_str = text_modifier_fn(text_str)
                processed_entries.append((rel_path, out_str.encode("utf-8")))
                manifest.append({"file": rel_path, "type": "Text/Markdown", "status": "Humanized"})
            elif ext in EXTENSION_MAP and code_humanizer_fn is not None:
                code_str = raw_bytes.decode("utf-8", errors="replace")
                out_code = code_humanizer_fn(code_str, rel_path)
                processed_entries.append((rel_path, out_code.encode("utf-8")))
                manifest.append(
                    {"file": rel_path, "type": f"Code ({ext})", "status": "Comments humanized (100% runnable)"}
                )
            else:
                # Preserve binary/asset files intact in the hierarchy
                processed_entries.append((rel_path, raw_bytes))
                manifest.append({"file": rel_path, "type": "Asset", "status": "Preserved untouched"})

    return processed_entries, manifest
