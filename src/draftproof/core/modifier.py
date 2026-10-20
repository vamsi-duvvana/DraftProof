"""Core 19-Stage / 4-Phase Deterministic Text Transformation Engine (`modifier.py`).

Implements:
- Phase 0 ("scrubber"): Zero-Width Unicode & Homoglyph Purge + 38-Pattern AI Tell Scrubber
- Placeholder Protection (`_protect_latex`): Masks LaTeX math, commands, citations, URLs, numbers, and protected scientific terms
- Phase 1 ("main"):
  1. `_apply_phrase_rewrites`
  2. `_apply_synonyms` (with morphological inflection stemmer/conjugator, sentence-level collision blocker, and rolling FIFO memory)
  3. `_reorder_clauses`
  4. `_swap_determiners` (with FIFO memory buffer)
  5. `_split_compound_sentences` (grammar-safe subject pronoun verification)
  6. `_insert_hedge_words` (respecting `EXCLUDED_ING_NOUNS`)
  7. `_transform_voice` (Active <-> Passive voice inversion)
  8. `_fuse_sentences` (Adjacent short-line fusion for burstiness variance)
  9. `_inject_transitions` (Categorized transition phrase injection)
  10. `_reorder_within_clause` (Prepositional/adverbial phrase topicalization)
  11. `_nominalize` (Verb <-> Noun structural transformation)
  12. `_inject_appositives` (Definitional appositive clause injection, once per document)
  13. `_rotate_discourse_markers` (PDTB 2.0 connective rotation with non-repeating memory)
  14. `_coordinate_same_subject` (Same-subject clause coordination §7)
- Phase 2 ("post"):
  15. `_break_ngram_chains` & Source-Aware 5-Gram Winnowing Audit
  16. `_restore_latex`
  17. Safety Invariant Gates (`TellInvariantGate` & `FactInvariantGate`)
- Phase 3 ("citation"):
  18. `_maybe_add_citation` (Section-aware citation shielding)
"""

from __future__ import annotations

import collections
import random
import re
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

from draftproof.config import ConfigNamespace
from draftproof.core.invariants import AITellScrubber, FactInvariantGate, TellInvariantGate
from draftproof.core.rules import (
    CONJUNCTIONS,
    EXCLUDED_ING_NOUNS,
    PROTECTED_TERMS,
    STRUCTURAL_RULES,
    get_rules_for_preset,
)
from draftproof.core.watermark import purge_zero_width_and_homoglyphs


class MorphologicalStemmer:
    """Inflection stemmer and conjugator for matching plural, past, participle, and adverbial forms."""

    @staticmethod
    def analyze_inflection(word: str, synonyms_map: Dict[str, List[str]]) -> Tuple[Optional[str], str]:
        """Find base lemma in `synonyms_map` and return `(lemma, suffix_type)`."""
        low = word.lower()
        if low in synonyms_map:
            return low, "exact"
        if low.endswith("ily") and len(low) > 5:
            cand = low[:-3] + "y"
            if cand in synonyms_map:
                return cand, "ily"
        if low.endswith("ly") and len(low) > 4:
            cand = low[:-2]
            if cand in synonyms_map:
                return cand, "ly"
        if low.endswith("ied") and len(low) > 4:
            cand = low[:-3] + "y"
            if cand in synonyms_map:
                return cand, "ied"
        if low.endswith("ed") and len(low) > 4:
            for cand in (low[:-2], low[:-1]):
                if cand in synonyms_map:
                    return cand, "ed"
        if low.endswith("ing") and len(low) > 5 and low not in EXCLUDED_ING_NOUNS:
            for cand in (low[:-3], low[:-3] + "e"):
                if cand in synonyms_map:
                    return cand, "ing"
        if low.endswith("ies") and len(low) > 4:
            cand = low[:-3] + "y"
            if cand in synonyms_map:
                return cand, "ies"
        if low.endswith("es") and len(low) > 4:
            for cand in (low[:-2], low[:-1]):
                if cand in synonyms_map:
                    return cand, "es"
        if low.endswith("s") and not low.endswith("ss") and len(low) > 3:
            cand = low[:-1]
            if cand in synonyms_map:
                return cand, "s"
        return None, ""

    @staticmethod
    def inflect_replacement(replacement: str, suffix_type: str) -> str:
        """Conjugate a base replacement word to match `suffix_type` (`exact` returns as-is)."""
        if suffix_type == "exact" or " " in replacement:
            return replacement
        if suffix_type in ("s", "es", "ies"):
            if replacement.endswith("y") and len(replacement) > 2 and replacement[-2] not in "aeiou":
                return replacement[:-1] + "ies"
            if replacement.endswith(("s", "x", "z", "ch", "sh")):
                return replacement + "es"
            return replacement + "s"
        if suffix_type in ("ed", "ied"):
            if replacement.endswith("e"):
                return replacement + "d"
            if replacement.endswith("y") and len(replacement) > 2 and replacement[-2] not in "aeiou":
                return replacement[:-1] + "ied"
            return replacement + "ed"
        if suffix_type == "ing":
            if replacement.endswith("ie"):
                return replacement[:-2] + "ying"
            if replacement.endswith("e") and not replacement.endswith("ee"):
                return replacement[:-1] + "ing"
            return replacement + "ing"
        if suffix_type in ("ly", "ily"):
            if replacement.endswith("y"):
                return replacement[:-1] + "ily"
            if replacement.endswith("le"):
                return replacement[:-2] + "ly"
            if replacement.endswith("ic"):
                return replacement + "ally"
            return replacement + "ly"
        return replacement


class TextModifier:
    """19-Stage deterministic text humanizer and Turnitin Winnowing/AI detector evader."""

    # Shielded section titles where citations must NEVER be injected
    SHIELDED_SECTIONS: Set[str] = {
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

    def __init__(self, config: Optional[ConfigNamespace] = None, seed: Optional[int] = None) -> None:
        self.config = config or ConfigNamespace()
        actual_seed = seed if seed is not None else self.config.SEED
        self.rng = random.Random(actual_seed)

        self.rules = get_rules_for_preset(self.config.STYLE_PRESET)
        self.scrubber = AITellScrubber(style_preset=self.config.STYLE_PRESET)
        self.tell_gate = TellInvariantGate(style_preset=self.config.STYLE_PRESET)
        self.fact_gate = FactInvariantGate()

        # Anti-repetition memory structures
        self._recent_synonyms: Deque[str] = collections.deque(maxlen=self.config.FIFO_MEMORY_SIZE)
        self._recent_determiners: Deque[str] = collections.deque(maxlen=self.config.DETERMINER_MEMORY_SIZE)
        self._recent_transitions: Deque[str] = collections.deque(maxlen=8)
        self._used_appositives: Set[str] = set()
        self._used_discourse_replacements: Dict[str, Set[str]] = {}

        # Stage counters (including all 7 GodGuide stages + v2.0.0 telemetry)
        self.phrase_rewrite_count: int = 0
        self.synonym_swap_count: int = 0
        self.clause_reorder_count: int = 0
        self.determiner_swap_count: int = 0
        self.sentence_split_count: int = 0
        self.hedge_insert_count: int = 0
        self.ngram_break_count: int = 0
        self.voice_transform_count: int = 0
        self.sentence_fusion_count: int = 0
        self.transition_inject_count: int = 0
        self.clause_word_reorder_count: int = 0
        self.nominalization_count: int = 0
        self.appositive_count: int = 0
        self.discourse_rotate_count: int = 0
        self.subject_coordination_count: int = 0
        self.ai_tells_scrubbed_count: int = 0
        self.zero_width_purged_count: int = 0
        self.citation_insert_count: int = 0

        self.changes_log: List[Dict[str, Any]] = []
        self._placeholders: Dict[str, str] = {}
        self._ph_counter: int = 0

    def reset_document_state(self) -> None:
        """Reset per-document state trackers while keeping configuration."""
        self._recent_synonyms.clear()
        self._recent_determiners.clear()
        self._recent_transitions.clear()
        self._used_appositives.clear()
        self._used_discourse_replacements.clear()

    def get_telemetry_summary(self) -> Dict[str, int]:
        """Return dictionary of all transformation stage counts."""
        counts = {
            "AI Tells Scrubbed": self.ai_tells_scrubbed_count,
            "Zero-Width / Homoglyphs Purged": self.zero_width_purged_count,
            "Phrase Rewrites": self.phrase_rewrite_count,
            "Synonym Swaps": self.synonym_swap_count,
            "PDTB Discourse Rotations": self.discourse_rotate_count,
            "Voice Transforms": self.voice_transform_count,
            "Sentence Fusions": self.sentence_fusion_count,
            "Sentence Splits": self.sentence_split_count,
            "Clause Reorders": self.clause_reorder_count,
            "Clause Word Reorders": self.clause_word_reorder_count,
            "Determiner Swaps": self.determiner_swap_count,
            "Transition Injections": self.transition_inject_count,
            "Nominalizations": self.nominalization_count,
            "Subject Coordinations": self.subject_coordination_count,
            "Hedge / Qualifier Inserts": self.hedge_insert_count,
            "Appositive Injections": self.appositive_count,
            "5-Gram Audit Breaks": self.ngram_break_count,
            "Citations Inserted": self.citation_insert_count,
        }
        counts["Total Transformations"] = sum(counts.values())
        return counts

    # ═══════════════════════════════════════════════════════════════════════════
    # PLACEHOLDER PROTECTION & UNMASKING
    # ═══════════════════════════════════════════════════════════════════════════

    def _new_placeholder(self, raw_token: str) -> str:
        key = f"\x00PH{self._ph_counter:04d}\x00"
        self._ph_counter += 1
        self._placeholders[key] = raw_token
        return key

    def _protect_latex(self, text: str) -> str:
        """Step 1: Mask LaTeX math, commands, markdown code, URLs, numbers, citations, and protected terms."""
        self._placeholders = {}
        self._ph_counter = 0
        protected = text

        # 1. Display & inline math + LaTeX environments
        math_patterns = [
            r"\$\$[\s\S]*?\$\$",
            r"\$[^$\n]+\$",
            r"\\\[[\s\S]*?\\\]",
            r"\\\([\s\S]*?\\\)",
            r"`[^`\n]+`",
            r"https?://[^\s)\]>]+",
        ]
        for pat in math_patterns:
            protected = re.sub(pat, lambda m: self._new_placeholder(m.group(0)), protected)

        # 2. LaTeX commands with arguments (\cite{...}, \ref{...}, \textbf{...}, etc.) and standalone macros
        protected = re.sub(
            r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})+",
            lambda m: self._new_placeholder(m.group(0)),
            protected,
        )
        protected = re.sub(
            r"\\[a-zA-Z]+\b",
            lambda m: self._new_placeholder(m.group(0)),
            protected,
        )

        # 3. Bracketed numeric citations [1], [1, 2], and author-year parentheticals (Author, 2024)
        protected = re.sub(
            r"\[\d+(?:\s*[,–-]\s*\d+)*\]",
            lambda m: self._new_placeholder(m.group(0)),
            protected,
        )
        protected = re.sub(
            r"\([A-Z][a-zA-Z-]+(?:\s+et\s+al\.)?,\s*\d{4}[a-z]?\)",
            lambda m: self._new_placeholder(m.group(0)),
            protected,
        )

        # 4. Protected domain terms (Navier-Stokes, Crank-Nicolson, Black-Scholes, etc.)
        for term in sorted(PROTECTED_TERMS, key=len, reverse=True):
            escaped = re.escape(term)
            protected = re.sub(
                rf"\b{escaped}\b",
                lambda m: self._new_placeholder(m.group(0)),
                protected,
                flags=re.IGNORECASE,
            )

        # 5. Numeric values & percentages (so FactInvariantGate is 100% preserved)
        protected = re.sub(
            r"\b\d+(?:\.\d+)?%?(?:[eE][+-]?\d+)?\b",
            lambda m: self._new_placeholder(m.group(0)),
            protected,
        )

        return protected

    def _restore_latex(self, text: str) -> str:
        """Step 16: Restore all placeholders in reverse order and purge any stray NULL bytes."""
        restored = text
        # Restore in reverse creation order in case of nested placeholders
        for key in sorted(self._placeholders.keys(), reverse=True):
            restored = restored.replace(key, self._placeholders[key])
        # Guarantee zero NULL bytes remain
        restored = restored.replace("\x00", "")
        return restored

    @staticmethod
    def _match_casing(original: str, replacement: str) -> str:
        if not original or not replacement:
            return replacement
        if original.isupper() and len(original) > 1:
            return replacement.upper()
        if original[0].isupper():
            return replacement[0].upper() + replacement[1:]
        return replacement

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 1: LEXICAL, STRUCTURAL & SEMANTIC STAGES
    # ═══════════════════════════════════════════════════════════════════════════

    def _apply_phrase_rewrites(self, text: str) -> str:
        """Step 2: Multi-word phrase rewrites (destroys 4-5 rolling hash windows per match)."""
        if not self.config.ENABLE_PHRASE_REWRITES:
            return text
        out = text
        for pattern, replacement in self.rules["phrases"]:
            def _repl(m: re.Match[str]) -> str:
                if self.rng.random() > min(0.95, self.config.SYNONYM_AGGRESSIVENESS + 0.25):
                    return m.group(0)
                self.phrase_rewrite_count += 1
                return self._match_casing(m.group(0), replacement)

            out = re.sub(pattern, _repl, out, flags=re.IGNORECASE)
        return out

    def _apply_synonyms(self, text: str) -> str:
        """Step 3: Morphological synonym swapping with contextual repetition blocker and FIFO memory."""
        if not self.config.ENABLE_SYNONYM_SWAP or self.config.SYNONYM_AGGRESSIVENESS <= 0:
            return text

        synonyms_map: Dict[str, List[str]] = self.rules["synonyms"]
        # Split around placeholders so placeholders are never touched
        segments = re.split(r"(\x00PH\d{4}\x00)", text)
        existing_words: Set[str] = {
            w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", text)
        }

        def _word_replacer(m: re.Match[str]) -> str:
            word = m.group(0)
            lemma, suffix_type = MorphologicalStemmer.analyze_inflection(word, synonyms_map)
            if not lemma:
                return word
            if self.rng.random() > self.config.SYNONYM_AGGRESSIVENESS:
                return word

            candidates = synonyms_map.get(lemma, [])
            if not candidates:
                return word

            inflected_candidates = [
                MorphologicalStemmer.inflect_replacement(c, suffix_type) for c in candidates
            ]
            # Filter out candidates already in active sentence or in recent FIFO memory
            filtered = [
                c
                for c in inflected_candidates
                if c.lower() not in existing_words and c.lower() not in self._recent_synonyms
            ]
            if not filtered:
                filtered = [c for c in inflected_candidates if c.lower() not in existing_words]
            if not filtered:
                return word

            chosen = self.rng.choice(filtered)
            self._recent_synonyms.append(chosen.lower())
            existing_words.add(chosen.lower())
            self.synonym_swap_count += 1
            return self._match_casing(word, chosen)

        new_segments: List[str] = []
        for seg in segments:
            if seg.startswith("\x00PH"):
                new_segments.append(seg)
            else:
                new_segments.append(re.sub(r"\b[a-zA-Z]{3,}\b", _word_replacer, seg))
        return "".join(new_segments)

    def _reorder_clauses(self, text: str) -> str:
        """Step 4: Subordinate clause reordering triggered by conjunctions."""
        if not self.config.ENABLE_CLAUSE_REORDER or len(text) < 55:
            return text
        if self.rng.random() > min(0.85, self.config.WORD_REORDER_RATE + 0.15):
            return text

        for conj in CONJUNCTIONS:
            # Pattern: Main clause + conj + subordinate clause.
            pat = re.compile(
                rf"^([A-Z][^.?!,;{{}}]+?)\s+({re.escape(conj)}\s+[^.?!;{{}}]+?)([.?!])$"
            )
            m = pat.match(text.strip())
            if m:
                main_cl, sub_cl, punct = m.group(1).strip(), m.group(2).strip(), m.group(3)
                if len(main_cl.split()) >= 4 and len(sub_cl.split()) >= 4:
                    main_lower = (
                        main_cl[0].lower() + main_cl[1:]
                        if not (len(main_cl) > 1 and main_cl[1].isupper())
                        else main_cl
                    )
                    sub_cap = sub_cl[0].upper() + sub_cl[1:]
                    self.clause_reorder_count += 1
                    return f"{sub_cap}, {main_lower}{punct}"
        return text

    def _swap_determiners(self, text: str) -> str:
        """Step 5: Determiner swapping with FIFO repetition memory."""
        if not self.config.ENABLE_DETERMINER_SWAP:
            return text
        det_map: Dict[str, List[str]] = self.rules["determiners"]
        segments = re.split(r"(\x00PH\d{4}\x00)", text)

        def _det_repl(m: re.Match[str]) -> str:
            word = m.group(0)
            low = word.lower()
            if low not in det_map:
                return word
            if self.rng.random() > min(0.85, self.config.SYNONYM_AGGRESSIVENESS * 0.7):
                return word
            options = [opt for opt in det_map[low] if opt.lower() not in self._recent_determiners]
            if not options:
                options = det_map[low]
            chosen = self.rng.choice(options)
            self._recent_determiners.append(chosen.lower())
            self.determiner_swap_count += 1
            return self._match_casing(word, chosen)

        return "".join(
            seg if seg.startswith("\x00PH") else re.sub(r"\b[a-zA-Z]{3,}\b", _det_repl, seg)
            for seg in segments
        )

    def _split_compound_sentences(self, text: str) -> str:
        """Step 6: Grammar-safe compound sentence splitting (avoids Oxford commas/lists)."""
        if not self.config.ENABLE_SENTENCE_SPLIT or len(text) < 95:
            return text
        if self.rng.random() > min(0.75, self.config.SENTENCE_FUSION_RATE + 0.10):
            return text

        valid_subjects = "|".join(STRUCTURAL_RULES.get("compound_split_subjects", ["this", "it", "they", "we", "the"]))
        pat = re.compile(
            rf"([^.?!]+?),\s+(?:and|while|whereas)\s+((?:{valid_subjects})\b[^.?!]+[.?!])",
            re.IGNORECASE,
        )
        m = pat.search(text)
        if m:
            first_part = m.group(1).strip()
            second_part = m.group(2).strip()
            if len(first_part.split()) >= 6 and len(second_part.split()) >= 6:
                second_cap = second_part[0].upper() + second_part[1:]
                connector = "Additionally, " if self.rules["mode"] == "academic" else "At the same time, "
                if second_cap[0].isupper() and not (len(second_cap) > 1 and second_cap[1].isupper()):
                    second_cap = connector + second_cap[0].lower() + second_cap[1:]
                self.sentence_split_count += 1
                return text[: m.start()] + f"{first_part}. {second_cap}" + text[m.end() :]
        return text

    def _insert_hedge_words(self, text: str) -> str:
        """Step 7: Insert hedging adverbs after auxiliary verbs or introductory commas."""
        if not self.config.ENABLE_HEDGE_INJECT or len(text) < 65:
            return text
        if self.rng.random() > min(0.75, self.config.SYNONYM_AGGRESSIVENESS * 0.45):
            return text

        hedges = self.rules["hedge_words"]
        if not hedges:
            return text

        # Look for auxiliary verb + verb/participle where second word is not an excluded -ing noun
        m = re.search(r"\b(is|are|was|were|can\s+be|may\s+be|has\s+been|have\s+been)\s+([a-z]{4,})\b", text)
        if m:
            aux, next_word = m.group(1), m.group(2)
            if next_word.lower() not in EXCLUDED_ING_NOUNS and next_word.lower() not in hedges:
                hedge = self.rng.choice(hedges)
                if hedge.lower() not in text.lower():
                    self.hedge_insert_count += 1
                    return text[: m.start()] + f"{aux} {hedge} {next_word}" + text[m.end() :]
        return text

    def _break_ngram_chains(self, text: str, source_text: Optional[str] = None) -> str:
        """Step 8 & Post-Pass: Source-Aware 5-Gram Audit & Chain Breaker."""
        if not self.config.ENABLE_NGRAM_AUDIT:
            return text

        compare_ref = source_text or text
        ref_words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{2,}\b", compare_ref)]
        if len(ref_words) < 5:
            return text

        ref_5grams: Set[Tuple[str, ...]] = {
            tuple(ref_words[i : i + 5]) for i in range(len(ref_words) - 4)
        }

        cur_words = re.findall(r"\b[a-zA-Z]{2,}\b", text)
        if len(cur_words) < 5:
            return text

        # Find if any 5-gram from source survived in text
        surviving_ngram: Optional[Tuple[str, ...]] = None
        for i in range(len(cur_words) - 4):
            gram = tuple(w.lower() for w in cur_words[i : i + 5])
            if gram in ref_5grams:
                surviving_ngram = tuple(cur_words[i : i + 5])
                break

        if not surviving_ngram:
            return text

        # Disrupt surviving 5-gram by synonymizing a word inside it or injecting a qualifier/parenthetical
        synonyms_map = self.rules["synonyms"]
        out = text
        for tok in surviving_ngram:
            lemma, suffix_type = MorphologicalStemmer.analyze_inflection(tok, synonyms_map)
            if lemma and synonyms_map.get(lemma):
                rep = MorphologicalStemmer.inflect_replacement(
                    self.rng.choice(synonyms_map[lemma]), suffix_type
                )
                rep_cased = self._match_casing(tok, rep)
                new_out = re.sub(rf"\b{re.escape(tok)}\b", rep_cased, out, count=1)
                if new_out != out:
                    self.ngram_break_count += 1
                    return new_out

        # Fallback: insert a safe parenthetical after comma or qualifier before a long content word
        inserts = self.rules["ngram_inserts"]
        if inserts and "," in out:
            ins = self.rng.choice(inserts)
            if ins.lower() not in out.lower():
                self.ngram_break_count += 1
                return out.replace(",", f", {ins},", 1)

        qualifiers = self.rules["qualifiers"]
        for tok in surviving_ngram[1:4]:
            if len(tok) >= 6 and tok.lower() not in EXCLUDED_ING_NOUNS and not tok.lower().endswith("ly"):
                qual = self.rng.choice(qualifiers)
                if qual.lower() not in out.lower():
                    new_out = re.sub(rf"\b{re.escape(tok)}\b", f"{qual} {tok}", out, count=1)
                    if new_out != out:
                        self.ngram_break_count += 1
                        return new_out
        return out

    # ═══════════════════════════════════════════════════════════════════════════
    # GODGUIDE EXTENDED STAGES (STAGES A–G + v2.0.0 COORDINATION)
    # ═══════════════════════════════════════════════════════════════════════════

    def _transform_voice(self, text: str) -> str:
        """Stage A: Active <-> Passive Voice Transformation (attacks Winnowing & stylometric uniformity)."""
        if not self.config.ENABLE_VOICE_TRANSFORM or len(text) < 60:
            return text
        if self.rng.random() > self.config.VOICE_TRANSFORM_RATE:
            return text
        # Skip sentences with coordinating conjunctions to prevent clause mangling (v1.3.0 rule)
        if re.search(r",\s*\b(?:and|but|or)\b", text, flags=re.IGNORECASE):
            return text

        voice_verbs: Dict[str, str] = STRUCTURAL_RULES.get("voice_verbs", {})
        passive_to_active: Dict[str, str] = STRUCTURAL_RULES.get("passive_to_active_verbs", {})

        # 1. Active -> Passive: "We/The authors/Researchers <verb> <object>"
        for active_v, passive_v in voice_verbs.items():
            pat = re.compile(
                rf"\b(We|The authors|The researchers|Our team|This study)\s+{re.escape(active_v)}\s+(the\s+[a-zA-Z0-9_-]+(?:\s+[a-zA-Z0-9_-]+){{0,3}})",
                re.IGNORECASE,
            )
            m = pat.search(text)
            if m:
                obj = m.group(2).strip()
                obj_cased = obj[0].upper() + obj[1:] if m.start() == 0 else obj
                is_plural = obj.split()[-1].endswith("s") and not obj.split()[-1].endswith("ss")
                aux_passive = passive_v.replace("was ", "were ") if is_plural else passive_v
                self.voice_transform_count += 1
                return text[: m.start()] + f"{obj_cased} {aux_passive}" + text[m.end() :]

        # 2. Passive -> Active: "<Object> was <verb> by <Subject>"
        for pass_phrase, act_v in passive_to_active.items():
            pat = re.compile(
                rf"\b(The\s+[a-zA-Z]+(?:\s+[a-zA-Z]+)?)\s+{re.escape(pass_phrase)}\s+(researchers|scientists|investigators|the authors|scholars)\b",
                re.IGNORECASE,
            )
            m = pat.search(text)
            if m:
                obj, subj = m.group(1).strip(), m.group(2).strip()
                subj_cased = subj[0].upper() + subj[1:] if m.start() == 0 else subj
                obj_low = obj[0].lower() + obj[1:]
                self.voice_transform_count += 1
                return text[: m.start()] + f"{subj_cased} {act_v} {obj_low}" + text[m.end() :]

        return text

    def _fuse_sentences(self, text: str, context_lines: Optional[List[str]] = None) -> str:
        """Stage B: Sentence Fusion (Anti-Burstiness Weapon merging short adjacent sentences)."""
        if not self.config.ENABLE_SENTENCE_FUSION:
            return text

        connectors = STRUCTURAL_RULES.get("fusion_connectors", {}).get(
            self.rules["mode"], [", which consequently", ", and as a result,"]
        )

        # Fuse short adjacent sentences within the same text block
        sentences = re.split(r"(?<=[.!?])\s+", text)
        if len(sentences) >= 2:
            out_sents: List[str] = []
            idx = 0
            while idx < len(sentences):
                cur = sentences[idx]
                if (
                    idx + 1 < len(sentences)
                    and 15 <= len(cur) < 85
                    and 15 <= len(sentences[idx + 1]) < 85
                    and cur.endswith(".")
                    and self.rng.random() <= self.config.SENTENCE_FUSION_RATE
                ):
                    nxt = sentences[idx + 1].lstrip()
                    if nxt and nxt[0].isupper() and not (len(nxt) > 1 and nxt[1].isupper()):
                        conn = self.rng.choice(connectors)
                        nxt_low = nxt[0].lower() + nxt[1:]
                        fused = f"{cur[:-1]}{conn} {nxt_low}"
                        out_sents.append(fused)
                        self.sentence_fusion_count += 1
                        idx += 2
                        continue
                out_sents.append(cur)
                idx += 1
            return " ".join(out_sents)

        return text

    def _inject_transitions(self, text: str) -> str:
        """Stage C: Categorized Transition Phrase Injection (Anti-Perplexity Weapon)."""
        if not self.config.ENABLE_TRANSITION_INJECT or len(text) < 70:
            return text
        if self.rng.random() > self.config.TRANSITION_INJECT_RATE:
            return text

        # Do not inject if sentence already starts with a transition followed by comma
        if re.match(r"^[A-Z][a-z]+(?:\s+[a-z]+){0,2},", text.strip()):
            return text

        transitions_dict: Dict[str, List[str]] = self.rules["transitions"]
        all_candidates = [
            phrase
            for cat_list in transitions_dict.values()
            for phrase in cat_list
            if phrase.lower() not in self._recent_transitions
        ]
        if not all_candidates:
            return text

        stripped = text.lstrip()
        if not stripped or not stripped[0].isupper():
            return text
        # Avoid decapitalizing acronyms or "I "
        first_word = stripped.split()[0].rstrip(",.")
        if len(first_word) > 1 and first_word[1:].isupper():
            return text
        if first_word == "I":
            return text

        chosen = self.rng.choice(all_candidates)
        self._recent_transitions.append(chosen.lower())
        leading_ws = text[: len(text) - len(stripped)]
        lowered = stripped[0].lower() + stripped[1:]
        self.transition_inject_count += 1
        return f"{leading_ws}{chosen} {lowered}"

    def _reorder_within_clause(self, text: str) -> str:
        """Stage D: Clause-Level Word Reordering (Karp-Rabin Order-Dependent Hash Destroyer)."""
        if not self.config.ENABLE_WORD_REORDER or len(text) < 75:
            return text
        if self.rng.random() > self.config.WORD_REORDER_RATE:
            return text

        preps = "|".join(STRUCTURAL_RULES.get("clause_reorder_prepositions", ["In", "For", "Using", "By", "With", "Through"]))
        # Pattern 1: Front prepositional phrase -> move to end or mid-clause
        pat_front = re.compile(rf"^((?:{preps})\s+[^,.\n]{{6,40}}),\s+([a-z][^.?!\n]{{20,}})([.?!])$")
        m = pat_front.match(text.strip())
        if m:
            prep_phrase, main_clause, punct = m.group(1).strip(), m.group(2).strip(), m.group(3)
            prep_low = prep_phrase[0].lower() + prep_phrase[1:]
            main_cap = main_clause[0].upper() + main_clause[1:]
            self.clause_word_reorder_count += 1
            return f"{main_cap} {prep_low}{punct}"

        # Pattern 2: End-position prepositional modifier -> topicalize to front
        pat_end = re.compile(
            r"^([A-Z][^.?!,\n]{20,65}?)\s+((?:by means of|through the use of|for the purpose of|with the aid of)\s+[^.?!,\n]{5,35})([.?!])$"
        )
        m2 = pat_end.match(text.strip())
        if m2:
            main_clause, prep_phrase, punct = m2.group(1).strip(), m2.group(2).strip(), m2.group(3)
            first_w = main_clause.split()[0]
            if not (len(first_w) > 1 and first_w[1:].isupper()) and first_w != "I":
                prep_cap = prep_phrase[0].upper() + prep_phrase[1:]
                main_low = main_clause[0].lower() + main_clause[1:]
                self.clause_word_reorder_count += 1
                return f"{prep_cap}, {main_low}{punct}"

        return text

    def _nominalize(self, text: str) -> str:
        """Stage E: Nominalization / De-nominalization (Verb <-> Noun Structure Destroyer)."""
        if not self.config.ENABLE_NOMINALIZATION or len(text) < 65:
            return text
        if self.rng.random() > self.config.NOMINALIZATION_RATE:
            return text

        nom_rules = STRUCTURAL_RULES.get("nominalizations", {})
        v2n: Dict[str, str] = nom_rules.get("verb_to_noun", {})
        n2v: Dict[str, str] = nom_rules.get("noun_to_verb", {})

        # Noun -> Verb ("The computation of X" -> "Computing X")
        for noun_phrase, verb_gerund in n2v.items():
            pat = re.compile(rf"\b{re.escape(noun_phrase)}\b", re.IGNORECASE)
            m = pat.search(text)
            if m:
                rep = self._match_casing(m.group(0), verb_gerund)
                self.nominalization_count += 1
                return text[: m.start()] + rep + text[m.end() :]

        # Verb -> Noun ("We investigated the X" -> "We conducted an investigation of the X")
        for verb_past, noun_expansion in v2n.items():
            pat = re.compile(
                rf"\b(We|The authors|Researchers|This study)\s+{re.escape(verb_past)}\s+(the\b)",
                re.IGNORECASE,
            )
            m = pat.search(text)
            if m:
                subj, det = m.group(1), m.group(2)
                self.nominalization_count += 1
                return text[: m.start()] + f"{subj} {noun_expansion} {det}" + text[m.end() :]

        return text

    def _inject_appositives(self, text: str) -> str:
        """Stage F: Appositive Clause Injection (Entropy Bomb — max once per term per document)."""
        if not self.config.ENABLE_APPOSITIVE or len(text) < 50:
            return text
        if self.rng.random() > self.config.APPOSITIVE_RATE:
            return text

        appositives: Dict[str, str] = self.rules["appositives"]
        for term, definition in appositives.items():
            term_low = term.lower()
            if term_low in self._used_appositives:
                continue
            pat = re.compile(rf"\b({re.escape(term)}(?:\s+method|\s+scheme|\s+model)?)\b(?!\s*,)", re.IGNORECASE)
            m = pat.search(text)
            if m:
                self._used_appositives.add(term_low)
                self.appositive_count += 1
                matched = m.group(1)
                return text[: m.start()] + f"{matched}, {definition}," + text[m.end() :]
        return text

    def _rotate_discourse_markers(self, text: str) -> str:
        """Stage G: PDTB 2.0 Discourse Marker Rotation (Anti-Repetition Shield)."""
        if not self.config.ENABLE_DISCOURSE_ROTATE:
            return text

        markers_map: Dict[str, List[str]] = self.rules["discourse_markers"]
        out = text
        for marker, replacements in markers_map.items():
            pat = re.compile(rf"\b{re.escape(marker)}\s*,", re.IGNORECASE)
            m = pat.search(out)
            if m and self.rng.random() <= self.config.DISCOURSE_ROTATE_RATE:
                used = self._used_discourse_replacements.setdefault(marker.lower(), set())
                available = [r for r in replacements if r.lower() not in used]
                if not available:
                    used.clear()
                    available = list(replacements)
                chosen = self.rng.choice(available)
                used.add(chosen.lower())
                rep_cased = self._match_casing(m.group(0).rstrip(","), chosen) + ","
                out = out[: m.start()] + rep_cased + out[m.end() :]
                self.discourse_rotate_count += 1
                break
        return out

    def _coordinate_same_subject(self, text: str) -> str:
        """v2.0.0 Stage: Same-Subject Clause Coordination (§7).

        Detects repeated subject pronouns/nouns across adjacent sentences ("The model processes X.
        The model also evaluates Y.") and coordinates them into a natural compound predicate.
        """
        if not self.config.ENABLE_SUBJECT_COORDINATION:
            return text
        if self.rng.random() > self.config.SUBJECT_COORDINATION_RATE:
            return text

        pat = re.compile(
            r"\b(The\s+[a-zA-Z]+|This\s+[a-zA-Z]+|It|We|They)\s+([^.?!]{10,65})\.\s+\1\s+(?:also\s+|further\s+|then\s+)?([a-z][^.?!]{8,65}[.?!])",
            re.IGNORECASE,
        )
        m = pat.search(text)
        if m:
            subj, pred1, pred2 = m.group(1), m.group(2).strip(), m.group(3).strip()
            self.subject_coordination_count += 1
            return text[: m.start()] + f"{subj} {pred1} and {pred2}" + text[m.end() :]
        return text

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 3: SECTION-AWARE CITATION SHIELDING
    # ═══════════════════════════════════════════════════════════════════════════

    def _maybe_add_citation(
        self,
        text: str,
        section_name: Optional[str] = None,
        citation_key: Optional[str] = None,
    ) -> str:
        """Step 17: Section-aware citation insertion (shields Abstract, Intro, Conclusion, etc.)."""
        if not citation_key or self.config.INSERT_CITATIONS.lower() == "off":
            return text
        if section_name and section_name.strip().lower() in self.SHIELDED_SECTIONS:
            return text
        stripped = text.rstrip()
        if not stripped.endswith(".") or len(stripped) < 55:
            return text
        # Do not double-cite
        if "\\cite" in stripped or re.search(r"\[\d+\]\.$", stripped):
            return text
        self.citation_insert_count += 1
        return f"{stripped[:-1]} {citation_key}."

    # ═══════════════════════════════════════════════════════════════════════════
    # FULL CONVEYOR BELT EXECUTION (`modify_line` & `modify_text`)
    # ═══════════════════════════════════════════════════════════════════════════

    def _run_core_pipeline_once(
        self,
        raw_line: str,
        context_lines: Optional[List[str]] = None,
        section_name: Optional[str] = None,
        citation_key: Optional[str] = None,
        original_source: Optional[str] = None,
    ) -> str:
        ref_source = original_source or raw_line
        working = self._protect_latex(raw_line)

        # Split multi-sentence lines so sentence-level stages fire accurately on each sentence
        sentences = re.split(r"(?<=[.!?])\s+", working)
        transformed_sentences: List[str] = []

        for s in sentences:
            if not s.strip():
                transformed_sentences.append(s)
                continue
            cur = s
            # Step 2: Phrase rewrites
            cur = self._apply_phrase_rewrites(cur)
            # Step 3: Morphological synonyms
            cur = self._apply_synonyms(cur)
            # Step 4: Clause reorder
            cur = self._reorder_clauses(cur)
            # Step 5: Determiner swap
            cur = self._swap_determiners(cur)
            # Step 6: Compound sentence split
            cur = self._split_compound_sentences(cur)
            # Step 7: Hedge word insertion
            cur = self._insert_hedge_words(cur)
            # Step 9 (Stage A): Active <-> Passive voice transform
            cur = self._transform_voice(cur)
            # Step 11 (Stage C): Transition phrase injection
            cur = self._inject_transitions(cur)
            # Step 12 (Stage D): Clause-level word reordering
            cur = self._reorder_within_clause(cur)
            # Step 13 (Stage E): Nominalization
            cur = self._nominalize(cur)
            # Step 14 (Stage F): Appositive injection
            cur = self._inject_appositives(cur)
            # Step 15 (Stage G): PDTB 2.0 discourse marker rotation
            cur = self._rotate_discourse_markers(cur)
            # Step 8 + Post-Pass: Source-aware 5-gram audit comparing cur against original un-scrubbed source
            cur = self._break_ngram_chains(cur, source_text=ref_source)
            transformed_sentences.append(cur)

        working = " ".join(transformed_sentences)

        # Step 10 (Stage B): Sentence fusion across adjacent short sentences
        working = self._fuse_sentences(working, context_lines=context_lines)
        # Same-Subject Clause Coordination (§7)
        working = self._coordinate_same_subject(working)

        # Step 16: Restore masked LaTeX & protected placeholders
        restored = self._restore_latex(working)

        # Final Source-Aware 5-Gram Audit against original raw_line
        if self.config.ENABLE_NGRAM_AUDIT and "\x00" not in restored and "\\" not in restored:
            restored = self._break_ngram_chains(restored, source_text=ref_source)

        # Step 17: Section-aware citation shielding
        restored = self._maybe_add_citation(
            restored, section_name=section_name, citation_key=citation_key
        )
        return restored

    def modify_line(
        self,
        line: str,
        context_lines: Optional[List[str]] = None,
        section_name: Optional[str] = None,
        citation_key: Optional[str] = None,
    ) -> str:
        """Execute the full 4-phase transformation pipeline on a line/paragraph with invariant gates."""
        if not line or not line.strip():
            return line

        # Phase 0 ("scrubber"): Purge zero-width Unicode, normalize homoglyphs, and scrub 38 AI tells
        working_input = line
        if self.config.ENABLE_ZERO_WIDTH_PURGE:
            working_input, zw_cnt, hg_cnt, _ = purge_zero_width_and_homoglyphs(working_input)
            self.zero_width_purged_count += zw_cnt + hg_cnt

        if self.config.ENABLE_AI_TELL_SCRUBBER:
            scrub_res = self.scrubber.scrub(working_input, clean_em_dashes=True)
            working_input = scrub_res.text
            self.ai_tells_scrubbed_count += (
                scrub_res.tells_removed
                + scrub_res.em_dashes_cleaned
                + scrub_res.chatbot_residues_stripped
            )

        if self.config.INTENSITY <= 0:
            return working_input

        # Up to 3 attempts to satisfy TellInvariantGate and FactInvariantGate
        best_candidate = working_input
        for _attempt in range(3):
            candidate = self._run_core_pipeline_once(
                working_input,
                context_lines=context_lines,
                section_name=section_name,
                citation_key=citation_key,
                original_source=line,
            )
            tell_ok = True
            fact_ok = True
            if self.config.ENABLE_TELL_INVARIANT_GATE:
                tell_ok, _, _ = self.tell_gate.verify(working_input, candidate)
            if self.config.ENABLE_FACT_INVARIANT_GATE:
                fact_ok, _ = self.fact_gate.verify(working_input, candidate)

            if tell_ok and fact_ok:
                best_candidate = candidate
                break

        if best_candidate != line:
            self.changes_log.append(
                {
                    "original": line,
                    "modified": best_candidate,
                    "section": section_name or "body",
                }
            )
        return best_candidate

    def modify_text(self, text: str, citation_engine: Optional[Any] = None) -> str:
        """Process a multi-paragraph text or Markdown/LaTeX document preserving paragraph boundaries."""
        if not text:
            return text
        self.reset_document_state()

        # Detect markdown/LaTeX section headers for section-aware citation shielding
        lines = text.splitlines(keepends=True)
        out_lines: List[str] = []
        current_section = "body"
        in_code_fence = False

        for idx, line in enumerate(lines):
            stripped = line.strip()
            # Protect fenced code blocks in Markdown
            if stripped.startswith("```"):
                in_code_fence = not in_code_fence
                out_lines.append(line)
                continue
            if in_code_fence:
                out_lines.append(line)
                continue

            # Track Markdown or LaTeX section headers
            md_sec = re.match(r"^#{1,4}\s+(.+)$", stripped)
            tex_sec = re.match(r"^\\(?:sub)*section\*?\{([^}]+)\}", stripped)
            if md_sec:
                current_section = md_sec.group(1).strip().lower()
                out_lines.append(line)
                continue
            if tex_sec:
                current_section = tex_sec.group(1).strip().lower()
                out_lines.append(line)
                continue

            if not stripped:
                out_lines.append(line)
                continue

            trailing_nl = line[len(line.rstrip("\r\n")) :]
            core_line = line.rstrip("\r\n")
            next_ctx = [lines[idx + 1].strip()] if idx + 1 < len(lines) else None
            modified_core = self.modify_line(
                core_line, context_lines=next_ctx, section_name=current_section
            )
            out_lines.append(modified_core + trailing_nl)

        result_text = "".join(out_lines)
        if citation_engine is not None and self.config.INSERT_CITATIONS.lower() != "off":
            cite_res = citation_engine.insert_citations(
                result_text,
                style=self.config.INSERT_CITATIONS,
                count=self.config.CITATION_COUNT,
                discipline=self.config.DISCIPLINE,
            )
            result_text = cite_res.cited_text
            self.citation_insert_count += cite_res.citations_inserted

        return result_text
