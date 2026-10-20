"""Unit tests for hierarchical academic taxonomy, `__prompt__` metadata stripping, and vocab hygiene."""

from __future__ import annotations

import json

from draftproof.core.rules import (
    ACADEMIC_SYNONYMS,
    ACADEMIC_TAXONOMY,
    CONVERSATIONAL_SYNONYMS,
    FORBIDDEN_OUTPUT_VOCAB,
    RULES_DIR,
)


def test_all_json_rule_files_contain_prompt_metadata() -> None:
    """Every JSON rule file under `rules/` must include `__prompt__` metadata per ARCHITECTURE_RULES.md."""
    json_files = list(RULES_DIR.rglob("*.json"))
    assert len(json_files) >= 25
    for jf in json_files:
        raw = json.loads(jf.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            assert "__prompt__" in raw, f"Missing __prompt__ key in object {jf}"
        elif isinstance(raw, list):
            assert len(raw) >= 1 and isinstance(raw[0], dict) and "__prompt__" in raw[0], (
                f"Missing index-0 __prompt__ block in list {jf}"
            )


def test_academic_taxonomy_disciplines_loaded_without_prompt_leak() -> None:
    """Recursive taxonomy loader must load all 5 core disciplines and strip `__prompt__`."""
    expected_folders = {
        "computer_science",
        "engineering_physics",
        "mathematics_statistics",
        "quantitative_finance",
        "medical_life_sciences",
    }
    assert expected_folders.issubset(set(ACADEMIC_TAXONOMY.keys()))
    for folder, subfields in ACADEMIC_TAXONOMY.items():
        assert len(subfields) >= 2, f"Discipline {folder} should have >=2 subfields"
        for sf in subfields:
            assert "__prompt__" not in sf
            assert "subfield_id" in sf
            assert "keywords" in sf and len(sf["keywords"]) >= 5
            assert "authors" in sf and len(sf["authors"]) >= 3
            assert "journals" in sf and len(sf["journals"]) >= 3


def test_vocab_hygiene_firewall_blocks_forbidden_ai_words() -> None:
    """Load-time vocab hygiene firewall must ensure no forbidden AI word appears in synonym outputs."""
    lower_forbidden = {w.lower() for w in FORBIDDEN_OUTPUT_VOCAB}
    for syn_dict in (ACADEMIC_SYNONYMS, CONVERSATIONAL_SYNONYMS):
        for key, candidates in syn_dict.items():
            for cand in candidates:
                assert cand.lower() not in lower_forbidden, f"Forbidden word {cand} leaked in {key}"
