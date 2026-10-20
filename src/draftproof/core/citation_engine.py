"""Decoupled Hierarchical Discipline Citation Engine (`citation_engine.py`).

Scans sentences against `ACADEMIC_TAXONOMY` (`rules/academic/taxonomy/*`), supports
unified `Citation Count` (`Auto` or exact integer), section-aware citation shielding,
and generates matching BibTeX (`citations.bib`), LaTeX (`\\cite{key}`), and structured
JSON (`citations.json`) reference packages.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from draftproof.core.rules import ACADEMIC_GENERAL_TOPICS, ACADEMIC_TAXONOMY

DISCIPLINE_LABELS: Dict[str, str] = {
    "Auto-Detect Field": "auto",
    "Computer Science & AI": "computer_science",
    "Engineering & Physics": "engineering_physics",
    "Mathematics & Statistics": "mathematics_statistics",
    "Quantitative Finance & Economics": "quantitative_finance",
    "Medical & Life Sciences": "medical_life_sciences",
}

FOLDER_TO_LABEL: Dict[str, str] = {v: k for k, v in DISCIPLINE_LABELS.items() if v != "auto"}

SHIELDED_SECTION_HEADERS: Set[str] = {
    "abstract",
    "introduction",
    "conclusion",
    "conclusions",
    "title",
    "declarations",
    "acknowledgments",
    "acknowledgements",
    "appendix",
    "appendices",
    "references",
    "bibliography",
}


@dataclass
class ReferenceEntry:
    """Single generated scholarly bibliography reference."""

    index: int
    cite_key: str
    authors_formatted: str
    authors_bibtex: str
    author_short: str
    year: int
    title: str
    journal: str
    volume: int
    pages: str
    doi: str
    discipline: str
    subfield: str


@dataclass
class CitationResult:
    """Complete result returned by `CitationEngine.insert_citations()`."""

    original_text: str
    cited_text: str
    style: str
    detected_discipline: str
    citations_inserted: int
    references: List[ReferenceEntry] = field(default_factory=list)
    formatted_bibliography: str = ""
    bibtex_content: str = ""
    latex_bibitem_content: str = ""
    json_content: str = ""


class CitationEngine:
    """100% UI-decoupled academic citation placer and multi-format reference exporter."""

    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)
        self.taxonomy = ACADEMIC_TAXONOMY
        self.general_topics = ACADEMIC_GENERAL_TOPICS

    def list_disciplines(self) -> List[str]:
        """Return user-facing list of academic disciplines."""
        return list(DISCIPLINE_LABELS.keys())

    def detect_discipline_and_subfield(
        self, text: str, preferred_discipline: str = "Auto-Detect Field"
    ) -> Tuple[str, Dict[str, Any]]:
        """Score sentences against `ACADEMIC_TAXONOMY` and return `(discipline_label, best_subfield)`."""
        words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", text)]
        word_counts: Dict[str, int] = {}
        for w in words:
            word_counts[w] = word_counts.get(w, 0) + 1

        pref_folder = DISCIPLINE_LABELS.get(preferred_discipline, preferred_discipline.lower())
        candidate_folders = (
            [pref_folder]
            if pref_folder in self.taxonomy
            else list(self.taxonomy.keys())
        )

        best_score = -1
        best_folder = candidate_folders[0] if candidate_folders else "computer_science"
        best_subfield: Optional[Dict[str, Any]] = None

        for folder in candidate_folders:
            for subfield in self.taxonomy.get(folder, []):
                keywords = [k.lower() for k in subfield.get("keywords", [])]
                score = sum(word_counts.get(k, 0) for k in keywords)
                if score > best_score:
                    best_score = score
                    best_folder = folder
                    best_subfield = subfield

        if best_subfield is None:
            fallback = (
                self.general_topics[0]
                if self.general_topics
                else {
                    "subfield_id": "general_research",
                    "subfield_name": "Empirical Research",
                    "keywords": ["analysis", "model"],
                    "authors": [["Anderson", "R. K."], ["Mitchell", "T. M."]],
                    "journals": ["Journal of Applied Research"],
                    "topics": ["empirical modeling and structural validation"],
                }
            )
            return "General Academic Research", fallback

        label = FOLDER_TO_LABEL.get(best_folder, best_subfield.get("discipline", best_folder))
        return label, best_subfield

    def _build_reference(
        self, idx: int, subfield: Dict[str, Any], discipline_label: str, used_keys: Set[str]
    ) -> ReferenceEntry:
        authors_pool: List[List[str]] = subfield.get(
            "authors", [["Anderson", "R. K."], ["Mitchell", "T. M."]]
        )
        journals_pool: List[str] = subfield.get(
            "journals", ["Journal of Applied Research and Methodology"]
        )
        topics_pool: List[str] = subfield.get(
            "topics",
            subfield.get("title_templates", ["quantitative analysis of complex systems"]),
        )
        keywords_pool: List[str] = subfield.get("keywords", ["system", "model"])

        # Pick 1 or 2 authors deterministically
        primary_author = authors_pool[(idx - 1) % len(authors_pool)]
        secondary_author = authors_pool[(idx + 2) % len(authors_pool)]
        year = 2019 + ((idx * 3) % 8)  # 2019..2026

        last1, init1 = primary_author[0], primary_author[1]
        last2, init2 = secondary_author[0], secondary_author[1]
        if last1 != last2 and idx % 2 == 0:
            authors_formatted = f"{last1}, {init1}, & {last2}, {init2}"
            authors_bibtex = f"{last1}, {init1} and {last2}, {init2}"
            author_short = f"{last1} & {last2}"
        else:
            authors_formatted = f"{last1}, {init1}"
            authors_bibtex = f"{last1}, {init1}"
            author_short = last1

        raw_topic = topics_pool[(idx - 1) % len(topics_pool)]
        kw = keywords_pool[(idx - 1) % len(keywords_pool)]
        title_body = raw_topic.replace("{topic}", kw)
        title = title_body[0].upper() + title_body[1:]

        journal = journals_pool[(idx - 1) % len(journals_pool)]
        volume = 12 + (idx * 7) % 45
        start_page = 100 + (idx * 37) % 800
        pages = f"{start_page}--{start_page + 14}"

        clean_last = re.sub(r"[^a-zA-Z]", "", last1).lower()
        clean_kw = re.sub(r"[^a-zA-Z]", "", kw).lower()
        base_key = f"{clean_last}{year}{clean_kw}"
        cite_key = base_key
        suffix_ord = ord("a")
        while cite_key in used_keys:
            cite_key = f"{base_key}{chr(suffix_ord)}"
            suffix_ord += 1
        used_keys.add(cite_key)

        doi = f"10.1016/j.{clean_kw[:6]}.{year}.{1000 + idx:04d}"

        return ReferenceEntry(
            index=idx,
            cite_key=cite_key,
            authors_formatted=authors_formatted,
            authors_bibtex=authors_bibtex,
            author_short=author_short,
            year=year,
            title=title,
            journal=journal,
            volume=volume,
            pages=pages,
            doi=doi,
            discipline=discipline_label,
            subfield=str(subfield.get("subfield_name", "General")),
        )

    @staticmethod
    def _parse_target_count(count_input: str | int, eligible_sentence_count: int) -> int:
        if isinstance(count_input, int):
            return max(1, min(50, count_input))
        s = str(count_input).strip().lower()
        if s in ("auto", "", "contextual"):
            if eligible_sentence_count <= 0:
                return 0
            return max(1, min(15, (eligible_sentence_count + 2) // 3))
        m = re.search(r"\d+", s)
        if m:
            return max(1, min(50, int(m.group(0))))
        return max(1, min(10, (eligible_sentence_count + 2) // 3))

    @staticmethod
    def _format_inline_marker(ref: ReferenceEntry, style: str) -> str:
        norm = style.strip().lower()
        if "apa" in norm or "author" in norm:
            return f"({ref.author_short}, {ref.year})"
        if "latex" in norm or "cite" in norm or "bib" in norm:
            return f"\\cite{{{ref.cite_key}}}"
        return f"[{ref.index}]"

    @staticmethod
    def _compile_exports(references: List[ReferenceEntry], style: str) -> Tuple[str, str, str, str]:
        if not references:
            return "", "", "", "[]"

        is_apa = "apa" in style.lower() or "author" in style.lower()
        bib_lines: List[str] = []
        bibtex_blocks: List[str] = []
        latex_blocks: List[str] = []

        for ref in references:
            if is_apa:
                bib_lines.append(
                    f"{ref.authors_formatted} ({ref.year}). {ref.title}. "
                    f"*{ref.journal}*, {ref.volume}, {ref.pages.replace('--', '-')}. https://doi.org/{ref.doi}"
                )
            else:
                bib_lines.append(
                    f"[{ref.index}] {ref.authors_formatted}, \"{ref.title},\" "
                    f"*{ref.journal}*, vol. {ref.volume}, pp. {ref.pages.replace('--', '-')}, {ref.year}, doi: {ref.doi}."
                )

            bibtex_blocks.append(
                f"@article{{{ref.cite_key},\n"
                f"  author  = {{{ref.authors_bibtex}}},\n"
                f"  title   = {{{ref.title}}},\n"
                f"  journal = {{{ref.journal}}},\n"
                f"  year    = {{{ref.year}}},\n"
                f"  volume  = {{{ref.volume}}},\n"
                f"  pages   = {{{ref.pages}}},\n"
                f"  doi     = {{{ref.doi}}}\n"
                f"}}"
            )

            latex_blocks.append(
                f"\\bibitem{{{ref.cite_key}}}\n"
                f"{ref.authors_formatted}, ``{ref.title},'' \\textit{{{ref.journal}}}, "
                f"vol.~{ref.volume}, pp.~{ref.pages}, {ref.year}."
            )

        json_payload = json.dumps([asdict(r) for r in references], indent=2)
        return (
            "\n\n".join(bib_lines),
            "\n\n".join(bibtex_blocks),
            "\\begin{thebibliography}{99}\n\n" + "\n\n".join(latex_blocks) + "\n\n\\end{thebibliography}",
            json_payload,
        )

    def insert_citations(
        self,
        text: str,
        style: str = "IEEE [1]",
        count: str | int = "Auto",
        discipline: str = "Auto-Detect Field",
        respect_section_shielding: bool = True,
    ) -> CitationResult:
        """Scan `text`, insert contextual citations, and generate BibTeX/LaTeX/JSON packages."""
        if not text or not text.strip():
            return CitationResult(
                original_text=text,
                cited_text=text,
                style=style,
                detected_discipline=discipline,
                citations_inserted=0,
            )

        disc_label, best_subfield = self.detect_discipline_and_subfield(text, discipline)
        keywords_set = {k.lower() for k in best_subfield.get("keywords", [])}

        # Segment paragraphs and sentences while tracking section headers
        paragraphs = text.split("\n")
        current_section = "body"
        candidate_locations: List[Tuple[int, int, int]] = []  # (para_idx, sent_idx, relevance_score)
        para_sentences: List[List[str]] = []

        for p_idx, para in enumerate(paragraphs):
            stripped = para.strip()
            md_sec = re.match(r"^#{1,4}\s+(.+)$", stripped)
            tex_sec = re.match(r"^\\(?:sub)*section\*?\{([^}]+)\}", stripped)
            if md_sec:
                current_section = md_sec.group(1).strip().lower()
                para_sentences.append([para])
                continue
            if tex_sec:
                current_section = tex_sec.group(1).strip().lower()
                para_sentences.append([para])
                continue
            if stripped.lower() in SHIELDED_SECTION_HEADERS:
                current_section = stripped.lower()
                para_sentences.append([para])
                continue

            if not stripped or stripped.startswith(("```", "%", "\\begin", "\\end")):
                para_sentences.append([para])
                continue

            sents = re.split(r"(?<=[.!?])\s+", para)
            para_sentences.append(sents)

            if respect_section_shielding and current_section in SHIELDED_SECTION_HEADERS:
                continue

            for s_idx, sent in enumerate(sents):
                s_clean = sent.strip()
                if len(s_clean) < 40 or not s_clean.endswith("."):
                    continue
                if "\\cite{" in s_clean or re.search(r"\[\d+\]\.$", s_clean):
                    continue
                s_words = {w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", s_clean)}
                overlap = len(s_words & keywords_set)
                score = overlap * 10 + min(15, len(s_words) // 3)
                candidate_locations.append((p_idx, s_idx, score))

        # If all paragraphs were inside a shielded section (e.g., user pasted only an Abstract in Citation Inserter),
        # fall back to allowing all prose sentences so explicit citation insertion still works.
        if not candidate_locations and respect_section_shielding:
            return self.insert_citations(
                text,
                style=style,
                count=count,
                discipline=discipline,
                respect_section_shielding=False,
            )

        target_n = self._parse_target_count(count, len(candidate_locations))
        if target_n <= 0 or not candidate_locations:
            return CitationResult(
                original_text=text,
                cited_text=text,
                style=style,
                detected_discipline=disc_label,
                citations_inserted=0,
            )

        # Select top candidates distributed across the document
        actual_n = min(target_n, len(candidate_locations))
        if actual_n == len(candidate_locations):
            chosen_locs = candidate_locations
        else:
            # Rank by score and spread evenly across document order
            sorted_by_score = sorted(
                candidate_locations, key=lambda item: item[2], reverse=True
            )
            top_pool = sorted_by_score[: max(actual_n, min(len(sorted_by_score), actual_n * 2))]
            top_pool_ordered = sorted(top_pool, key=lambda item: (item[0], item[1]))
            step = max(1.0, len(top_pool_ordered) / actual_n)
            chosen_locs = [
                top_pool_ordered[min(len(top_pool_ordered) - 1, int(i * step))]
                for i in range(actual_n)
            ]
            # Deduplicate while preserving order
            seen_loc: Set[Tuple[int, int]] = set()
            deduped: List[Tuple[int, int, int]] = []
            for p_i, s_i, sc in chosen_locs:
                if (p_i, s_i) not in seen_loc:
                    seen_loc.add((p_i, s_i))
                    deduped.append((p_i, s_i, sc))
            for p_i, s_i, sc in sorted_by_score:
                if len(deduped) >= actual_n:
                    break
                if (p_i, s_i) not in seen_loc:
                    seen_loc.add((p_i, s_i))
                    deduped.append((p_i, s_i, sc))
            chosen_locs = sorted(deduped, key=lambda item: (item[0], item[1]))

        references: List[ReferenceEntry] = []
        used_keys: Set[str] = set()

        for ref_idx, (p_i, s_i, _sc) in enumerate(chosen_locs, start=1):
            ref = self._build_reference(ref_idx, best_subfield, disc_label, used_keys)
            references.append(ref)
            marker = self._format_inline_marker(ref, style)
            orig_sent = para_sentences[p_i][s_i].rstrip()
            if orig_sent.endswith("."):
                para_sentences[p_i][s_i] = f"{orig_sent[:-1]} {marker}."
            else:
                para_sentences[p_i][s_i] = f"{orig_sent} {marker}"

        cited_paragraphs = [" ".join(sents) for sents in para_sentences]
        cited_text = "\n".join(cited_paragraphs)

        formatted_bib, bibtex_str, latex_str, json_str = self._compile_exports(references, style)

        return CitationResult(
            original_text=text,
            cited_text=cited_text,
            style=style,
            detected_discipline=disc_label,
            citations_inserted=len(references),
            references=references,
            formatted_bibliography=formatted_bib,
            bibtex_content=bibtex_str,
            latex_bibitem_content=latex_str,
            json_content=json_str,
        )
