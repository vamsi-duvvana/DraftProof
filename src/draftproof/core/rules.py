"""Dynamic JSON rules and hierarchical academic discipline taxonomy loader.

Strictly enforces ARCHITECTURE_RULES.md:
- Strips `__prompt__` metadata blocks from all JSON dictionaries and arrays.
- Applies Load-Time Vocab Hygiene Firewall (`filter_output_vocab`) so forbidden AI
  tells can never be emitted as replacement targets.
- Recursively loads `rules/academic/taxonomy/<discipline>/<subfield>.json`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

RULES_DIR = Path(__file__).resolve().parents[3] / "rules"


def _strip_prompt_metadata(data: Any) -> Any:
    """Remove `__prompt__` root keys from dicts and index-0 `__prompt__` objects from lists."""
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if k != "__prompt__"}
    if isinstance(data, list):
        return [
            item
            for item in data
            if not (isinstance(item, dict) and "__prompt__" in item and len(item) == 1)
        ]
    return data


def load_json_rule(relative_path: str | Path) -> Any:
    """Load a JSON rule file relative to `rules/` and strip `__prompt__` metadata."""
    full_path = RULES_DIR / relative_path
    if not full_path.exists():
        raise FileNotFoundError(f"Rule file not found: {full_path}")
    with open(full_path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return _strip_prompt_metadata(raw)


def filter_output_vocab(
    synonyms: Dict[str, List[str]], forbidden_words: Set[str]
) -> Dict[str, List[str]]:
    """Load-Time Vocab Hygiene Firewall: strip any candidate containing a forbidden AI tell."""
    cleaned: Dict[str, List[str]] = {}
    lower_forbidden = {w.lower() for w in forbidden_words}
    for key, candidates in synonyms.items():
        if not isinstance(candidates, list):
            continue
        valid = [
            c
            for c in candidates
            if isinstance(c, str)
            and c.lower() not in lower_forbidden
            and not any(tok in lower_forbidden for tok in c.lower().split())
        ]
        if valid:
            cleaned[key] = valid
    return cleaned


def load_academic_taxonomy(taxonomy_root: Path | None = None) -> Dict[str, List[Dict[str, Any]]]:
    """Recursively walk `rules/academic/taxonomy/` and load all discipline subfields."""
    root = taxonomy_root or (RULES_DIR / "academic" / "taxonomy")
    taxonomy: Dict[str, List[Dict[str, Any]]] = {}
    if not root.exists():
        return taxonomy

    for discipline_dir in sorted(root.iterdir()):
        if not discipline_dir.is_dir():
            continue
        discipline_key = discipline_dir.name
        subfields: List[Dict[str, Any]] = []
        for json_file in sorted(discipline_dir.rglob("*.json")):
            with open(json_file, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            cleaned = _strip_prompt_metadata(raw)
            if isinstance(cleaned, list):
                for entry in cleaned:
                    if isinstance(entry, dict) and "subfield_id" in entry:
                        entry.setdefault("discipline_folder", discipline_key)
                        subfields.append(entry)
            elif isinstance(cleaned, dict) and "subfield_id" in cleaned:
                cleaned.setdefault("discipline_folder", discipline_key)
                subfields.append(cleaned)
        if subfields:
            taxonomy[discipline_key] = subfields
    return taxonomy


# Load core shared catalogs
AI_TELLS_DATA: Dict[str, Any] = load_json_rule("ai_tells.json")
FORBIDDEN_OUTPUT_VOCAB: Set[str] = set(AI_TELLS_DATA.get("forbidden_output_vocab", []))
ZERO_WIDTH_CODEPOINTS: List[str] = list(AI_TELLS_DATA.get("zero_width_codepoints", []))
HOMOGLYPH_MAP: Dict[str, str] = dict(AI_TELLS_DATA.get("homoglyph_map", {}))
CHATBOT_RESIDUE_PATTERNS: List[str] = list(AI_TELLS_DATA.get("chatbot_residue_patterns", []))
AI_TELL_PATTERNS: List[Dict[str, str]] = list(AI_TELLS_DATA.get("tell_patterns", []))

CONJUNCTIONS: List[str] = load_json_rule("conjunctions.json")
PROTECTED_TERMS: List[str] = load_json_rule("protected_terms.json")
EXCLUDED_ING_NOUNS: Set[str] = {w.lower() for w in load_json_rule("excluded_ing_nouns.json")}
STRUCTURAL_RULES: Dict[str, Any] = load_json_rule("structural_rules.json")
CODE_PERSONAS_DATA: Dict[str, Any] = load_json_rule("code/personas.json")

# Load Academic Preset Catalogs
ACADEMIC_SYNONYMS: Dict[str, List[str]] = filter_output_vocab(
    load_json_rule("academic/synonyms.json"), FORBIDDEN_OUTPUT_VOCAB
)
ACADEMIC_PHRASES: List[Tuple[str, str]] = [
    (pair[0], pair[1]) for pair in load_json_rule("academic/phrases.json")
]
ACADEMIC_DETERMINERS: Dict[str, List[str]] = load_json_rule("academic/determiners.json")
ACADEMIC_HEDGE_WORDS: List[str] = load_json_rule("academic/hedge_words.json")
ACADEMIC_QUALIFIERS: List[str] = load_json_rule("academic/qualifiers.json")
ACADEMIC_NGRAM_INSERTS: List[str] = load_json_rule("academic/ngram_inserts.json")
ACADEMIC_TRANSITIONS: Dict[str, List[str]] = load_json_rule("academic/transition_phrases.json")
ACADEMIC_DISCOURSE_MARKERS: Dict[str, List[str]] = load_json_rule("academic/discourse_markers.json")
ACADEMIC_APPOSITIVES: Dict[str, str] = load_json_rule("academic/appositives.json")
ACADEMIC_GENERAL_TOPICS: List[Dict[str, Any]] = load_json_rule("academic/general_academic_topics.json")
ACADEMIC_TAXONOMY: Dict[str, List[Dict[str, Any]]] = load_academic_taxonomy()

# Load Conversational Preset Catalogs
CONVERSATIONAL_SYNONYMS: Dict[str, List[str]] = filter_output_vocab(
    load_json_rule("conversational/synonyms.json"), FORBIDDEN_OUTPUT_VOCAB
)
CONVERSATIONAL_PHRASES: List[Tuple[str, str]] = [
    (pair[0], pair[1]) for pair in load_json_rule("conversational/phrases.json")
]
CONVERSATIONAL_DETERMINERS: Dict[str, List[str]] = load_json_rule("conversational/determiners.json")
CONVERSATIONAL_HEDGE_WORDS: List[str] = load_json_rule("conversational/hedge_words.json")
CONVERSATIONAL_QUALIFIERS: List[str] = load_json_rule("conversational/qualifiers.json")
CONVERSATIONAL_NGRAM_INSERTS: List[str] = load_json_rule("conversational/ngram_inserts.json")
CONVERSATIONAL_TRANSITIONS: Dict[str, List[str]] = load_json_rule("conversational/transition_phrases.json")
CONVERSATIONAL_DISCOURSE_MARKERS: Dict[str, List[str]] = load_json_rule("conversational/discourse_markers.json")


def get_rules_for_preset(preset: str = "conversational") -> Dict[str, Any]:
    """Return the active rule dictionary bundle for `academic`, `technical`, or `conversational`."""
    norm = (preset or "conversational").strip().lower()
    if norm.startswith("acad") or norm.startswith("tech") or norm.startswith("scholar"):
        return {
            "mode": "academic",
            "synonyms": ACADEMIC_SYNONYMS,
            "phrases": ACADEMIC_PHRASES,
            "determiners": ACADEMIC_DETERMINERS,
            "hedge_words": ACADEMIC_HEDGE_WORDS,
            "qualifiers": ACADEMIC_QUALIFIERS,
            "ngram_inserts": ACADEMIC_NGRAM_INSERTS,
            "transitions": ACADEMIC_TRANSITIONS,
            "discourse_markers": ACADEMIC_DISCOURSE_MARKERS,
            "appositives": ACADEMIC_APPOSITIVES,
        }
    return {
        "mode": "conversational",
        "synonyms": CONVERSATIONAL_SYNONYMS,
        "phrases": CONVERSATIONAL_PHRASES,
        "determiners": CONVERSATIONAL_DETERMINERS,
        "hedge_words": CONVERSATIONAL_HEDGE_WORDS,
        "qualifiers": CONVERSATIONAL_QUALIFIERS,
        "ngram_inserts": CONVERSATIONAL_NGRAM_INSERTS,
        "transitions": CONVERSATIONAL_TRANSITIONS,
        "discourse_markers": CONVERSATIONAL_DISCOURSE_MARKERS,
        "appositives": ACADEMIC_APPOSITIVES,
    }
