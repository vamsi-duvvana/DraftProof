"""Master 38-Pattern AI Tell Scrubber and Safety Invariant Gates (TellInvariantGate & FactInvariantGate)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from draftproof.core.rules import (
    AI_TELL_PATTERNS,
    CHATBOT_RESIDUE_PATTERNS,
    FORBIDDEN_OUTPUT_VOCAB,
)


@dataclass
class TellMatch:
    """Single detected AI tell occurrence."""

    tell_id: str
    category: str
    matched_text: str
    replacement: str
    span: Tuple[int, int]


@dataclass
class ScrubResult:
    """Result of running the 38-Pattern AI Tell Scrubber on a text block."""

    text: str
    tells_removed: int = 0
    em_dashes_cleaned: int = 0
    chatbot_residues_stripped: int = 0
    matches: List[TellMatch] = field(default_factory=list)


class AITellScrubber:
    """Deterministic 38-pattern AI tell scrubber and document-level residue cleaner."""

    def __init__(self, style_preset: str = "conversational") -> None:
        self.style_preset = (
            "academic"
            if str(style_preset).lower().startswith(("acad", "tech", "scholar"))
            else "conversational"
        )
        self._compiled_patterns = [
            (
                entry["id"],
                entry["category"],
                re.compile(entry["pattern"], re.IGNORECASE),
                entry.get(self.style_preset, entry.get("conversational", "")),
            )
            for entry in AI_TELL_PATTERNS
        ]
        self._compiled_residues = [
            re.compile(pat, re.IGNORECASE | re.MULTILINE) for pat in CHATBOT_RESIDUE_PATTERNS
        ]

    @staticmethod
    def _match_case(original: str, replacement: str) -> str:
        if not original or not replacement:
            return replacement
        if original[0].isupper() and replacement[0].islower():
            return replacement[0].upper() + replacement[1:]
        if original[0].islower() and replacement[0].isupper():
            return replacement[0].lower() + replacement[1:]
        return replacement

    def detect_tells(self, text: str) -> List[TellMatch]:
        """Return all AI tell matches currently present in `text`."""
        found: List[TellMatch] = []
        if not text:
            return found
        for tell_id, category, regex, replacement in self._compiled_patterns:
            for m in regex.finditer(text):
                found.append(
                    TellMatch(
                        tell_id=tell_id,
                        category=category,
                        matched_text=m.group(0),
                        replacement=self._match_case(m.group(0), replacement),
                        span=m.span(),
                    )
                )
        # Also detect standalone forbidden output vocabulary not caught by multi-word patterns
        already_covered = [m.span for m in found]
        for word_match in re.finditer(r"\b[a-zA-Z]{4,}\b", text):
            w_low = word_match.group(0).lower()
            if w_low in FORBIDDEN_OUTPUT_VOCAB:
                s, e = word_match.span()
                if not any(cs <= s and e <= ce for cs, ce in already_covered):
                    found.append(
                        TellMatch(
                            tell_id="VOCAB",
                            category="Forbidden AI Vocabulary",
                            matched_text=word_match.group(0),
                            replacement="",
                            span=(s, e),
                        )
                    )
        return found

    def count_tells(self, text: str) -> int:
        """Count total AI tell occurrences in `text`."""
        return len(self.detect_tells(text))

    def scrub(self, text: str, clean_em_dashes: bool = True) -> ScrubResult:
        """Deterministically scrub chatbot residues, all 38 AI tell patterns, and em-dashes."""
        if not text:
            return ScrubResult(text=text)

        working = text
        residues_removed = 0
        for res_re in self._compiled_residues:
            working, n = res_re.subn("", working)
            residues_removed += n

        # Strip decorative bold bullet lead-in colons while keeping term text
        matches_logged: List[TellMatch] = []
        tells_removed = 0

        for tell_id, category, regex, replacement in self._compiled_patterns:
            def _replacer(m: re.Match[str]) -> str:
                nonlocal tells_removed
                orig = m.group(0)
                rep = self._match_case(orig, replacement)
                tells_removed += 1
                matches_logged.append(
                    TellMatch(
                        tell_id=tell_id,
                        category=category,
                        matched_text=orig,
                        replacement=rep,
                        span=m.span(),
                    )
                )
                return rep

            working = regex.sub(_replacer, working)

        em_cleaned = 0
        if clean_em_dashes:
            # Replace spaced or unspaced em-dashes in prose with contextual comma
            def _em_repl(m: re.Match[str]) -> str:
                nonlocal em_cleaned
                em_cleaned += 1
                return ", "

            working = re.sub(r"\s*—\s*", _em_repl, working)

        # Normalize duplicate spaces/commas caused by replacements
        working = re.sub(r",\s*,", ",", working)
        working = re.sub(r"[ \t]{2,}", " ", working)
        return ScrubResult(
            text=working.strip() if text == text.strip() else working,
            tells_removed=tells_removed,
            em_dashes_cleaned=em_cleaned,
            chatbot_residues_stripped=residues_removed,
            matches=matches_logged,
        )


class TellInvariantGate:
    """Enforces the mathematical invariant `tells(output) <= tells(input)`."""

    def __init__(self, style_preset: str = "conversational") -> None:
        self.scrubber = AITellScrubber(style_preset=style_preset)

    def verify(self, input_text: str, output_text: str) -> Tuple[bool, int, int]:
        """Return `(passed, input_tells, output_tells)`."""
        in_tells = self.scrubber.count_tells(input_text)
        out_tells = self.scrubber.count_tells(output_text)
        return out_tells <= in_tells, in_tells, out_tells


class FactInvariantGate:
    """Guarantees 100% preservation of numeric values, bracketed citations, and LaTeX cites."""

    _NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?%?\b")
    _BRACKET_CITE_RE = re.compile(r"\[\d+(?:\s*[,–-]\s*\d+)*\]")
    _LATEX_CITE_RE = re.compile(r"\\cite[a-zA-Z]*\{[^}]+\}")

    @classmethod
    def extract_facts(cls, text: str) -> Tuple[Set[str], Set[str], Set[str]]:
        numbers = set(cls._NUMBER_RE.findall(text))
        brackets = set(cls._BRACKET_CITE_RE.findall(text))
        latex_cites = set(cls._LATEX_CITE_RE.findall(text))
        return numbers, brackets, latex_cites

    @classmethod
    def verify(cls, input_text: str, output_text: str) -> Tuple[bool, List[str]]:
        """Check that every number, bracketed citation, and LaTeX cite in `input_text` remains in `output_text`."""
        in_nums, in_brackets, in_cites = cls.extract_facts(input_text)
        out_nums, out_brackets, out_cites = cls.extract_facts(output_text)

        missing: List[str] = []
        for n in sorted(in_nums - out_nums):
            missing.append(f"number:{n}")
        for b in sorted(in_brackets - out_brackets):
            missing.append(f"citation:{b}")
        for c in sorted(in_cites - out_cites):
            missing.append(f"latex_cite:{c}")
        return len(missing) == 0, missing
