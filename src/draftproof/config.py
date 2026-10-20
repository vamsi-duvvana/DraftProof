"""Centralized configuration loader and intensity curve mapping for DraftProof."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GLOBAL_CONFIG_PATH = PROJECT_ROOT / "rules" / "global_config.json"
FALLBACK_GLOBAL_CONFIG_PATH = PROJECT_ROOT / "configs" / "global_config.json"


def _parse_bool(val: Any, default: bool = True) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return default
    return str(val).strip().lower() in ("true", "1", "yes", "on")


def compute_effective_aggressiveness(slider_intensity: float, exponent: float = 0.75) -> float:
    """Map UI slider percentage (0..100) to internal transformation rate using power/volume curve."""
    clamped = max(0.0, min(100.0, float(slider_intensity)))
    if clamped == 0.0:
        return 0.0
    return round((clamped / 100.0) ** exponent, 4)


def load_raw_global_config() -> Dict[str, Any]:
    """Load centralized global_config.json from rules/ or configs/."""
    for candidate in (DEFAULT_GLOBAL_CONFIG_PATH, FALLBACK_GLOBAL_CONFIG_PATH):
        if candidate.exists():
            with open(candidate, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if k != "__prompt__"}
    return {}


class ConfigNamespace:
    """Configuration container populated from JSON config and environment overrides."""

    def __init__(self, data: Optional[Dict[str, Any]] = None) -> None:
        raw_global = load_raw_global_config()
        stage_defaults = raw_global.get("stage_defaults", {})
        d: Dict[str, Any] = {**stage_defaults, **(data or {})}

        self.VERSION: str = str(raw_global.get("version", "2.0.0"))
        self.STYLE_PRESET: str = os.getenv(
            "DRAFTPROOF_STYLE_PRESET",
            str(d.get("style_preset", raw_global.get("default_style_preset", "conversational"))),
        ).lower()
        self.INTENSITY: float = float(
            os.getenv("DRAFTPROOF_INTENSITY", d.get("intensity", raw_global.get("default_intensity", 75)))
        )
        self.CURVE_EXPONENT: float = float(raw_global.get("intensity_curve_exponent", 0.75))
        self.SYNONYM_AGGRESSIVENESS: float = float(
            os.getenv(
                "DRAFTPROOF_SYNONYM_AGGRESSIVENESS",
                d.get(
                    "synonym_aggressiveness",
                    compute_effective_aggressiveness(self.INTENSITY, self.CURVE_EXPONENT),
                ),
            )
        )
        self.SEED: Optional[int] = (
            int(os.environ["DRAFTPROOF_SEED"])
            if "DRAFTPROOF_SEED" in os.environ
            else d.get("seed", 42)
        )
        self.FIFO_MEMORY_SIZE: int = int(raw_global.get("fifo_memory_size", 15))
        self.DETERMINER_MEMORY_SIZE: int = int(raw_global.get("determiner_memory_size", 8))

        # Safety & Watermark Scrubbers (v2.0.0)
        self.ENABLE_AI_TELL_SCRUBBER: bool = _parse_bool(
            os.getenv("DRAFTPROOF_AI_TELL_SCRUBBER", d.get("enable_ai_tell_scrubber", True))
        )
        self.ENABLE_ZERO_WIDTH_PURGE: bool = _parse_bool(
            os.getenv("DRAFTPROOF_ZERO_WIDTH_PURGE", d.get("enable_zero_width_purge", True))
        )
        self.ENABLE_WATERMARK_DISRUPT: bool = _parse_bool(
            os.getenv("DRAFTPROOF_WATERMARK_DISRUPT", d.get("enable_watermark_disrupt", True))
        )
        self.ENABLE_C2PA_STRIP: bool = _parse_bool(
            os.getenv("DRAFTPROOF_C2PA_STRIP", d.get("enable_c2pa_strip", True))
        )
        self.ENABLE_TELL_INVARIANT_GATE: bool = _parse_bool(
            os.getenv("DRAFTPROOF_TELL_INVARIANT_GATE", d.get("enable_tell_invariant_gate", True))
        )
        self.ENABLE_FACT_INVARIANT_GATE: bool = _parse_bool(
            os.getenv("DRAFTPROOF_FACT_INVARIANT_GATE", d.get("enable_fact_invariant_gate", True))
        )

        # Core Lexical & Structural Stages
        self.ENABLE_PHRASE_REWRITES: bool = _parse_bool(
            os.getenv("DRAFTPROOF_PHRASE_REWRITES", d.get("enable_phrase_rewrites", True))
        )
        self.ENABLE_SYNONYM_SWAP: bool = _parse_bool(
            os.getenv("DRAFTPROOF_SYNONYM_SWAP", d.get("enable_synonym_swap", True))
        )
        self.ENABLE_CLAUSE_REORDER: bool = _parse_bool(
            os.getenv("DRAFTPROOF_CLAUSE_REORDER", d.get("enable_clause_reorder", True))
        )
        self.ENABLE_DETERMINER_SWAP: bool = _parse_bool(
            os.getenv("DRAFTPROOF_DETERMINER_SWAP", d.get("enable_determiner_swap", True))
        )
        self.ENABLE_SENTENCE_SPLIT: bool = _parse_bool(
            os.getenv("DRAFTPROOF_SENTENCE_SPLIT", d.get("enable_sentence_split", True))
        )
        self.ENABLE_HEDGE_INJECT: bool = _parse_bool(
            os.getenv("DRAFTPROOF_HEDGE_INJECT", d.get("enable_hedge_inject", True))
        )
        self.ENABLE_NGRAM_AUDIT: bool = _parse_bool(
            os.getenv("DRAFTPROOF_NGRAM_AUDIT", d.get("enable_ngram_audit", True))
        )

        # Extended 7+1 Transformation Stages (GodGuide + v2.0.0)
        self.ENABLE_VOICE_TRANSFORM: bool = _parse_bool(
            os.getenv("DRAFTPROOF_VOICE_TRANSFORM", str(d.get("enable_voice_transform", True)))
        )
        self.ENABLE_SENTENCE_FUSION: bool = _parse_bool(
            os.getenv("DRAFTPROOF_SENTENCE_FUSION", str(d.get("enable_sentence_fusion", True)))
        )
        self.ENABLE_TRANSITION_INJECT: bool = _parse_bool(
            os.getenv("DRAFTPROOF_TRANSITION_INJECT", str(d.get("enable_transition_inject", True)))
        )
        self.ENABLE_WORD_REORDER: bool = _parse_bool(
            os.getenv("DRAFTPROOF_WORD_REORDER", str(d.get("enable_word_reorder", True)))
        )
        self.ENABLE_NOMINALIZATION: bool = _parse_bool(
            os.getenv("DRAFTPROOF_NOMINALIZATION", str(d.get("enable_nominalization", True)))
        )
        self.ENABLE_APPOSITIVE: bool = _parse_bool(
            os.getenv(
                "DRAFTPROOF_APPOSITIVE",
                str(d.get("enable_appositive", self.STYLE_PRESET != "academic")),
            )
        )
        self.ENABLE_DISCOURSE_ROTATE: bool = _parse_bool(
            os.getenv("DRAFTPROOF_DISCOURSE_ROTATE", str(d.get("enable_discourse_rotate", True)))
        )
        self.ENABLE_SUBJECT_COORDINATION: bool = _parse_bool(
            os.getenv("DRAFTPROOF_SUBJECT_COORDINATION", str(d.get("enable_subject_coordination", True)))
        )

        # Per-stage fire rates
        self.VOICE_TRANSFORM_RATE: float = float(
            os.getenv("DRAFTPROOF_VOICE_RATE", d.get("voice_transform_rate", 0.30))
        )
        self.SENTENCE_FUSION_RATE: float = float(
            os.getenv("DRAFTPROOF_FUSION_RATE", d.get("sentence_fusion_rate", 0.25))
        )
        self.TRANSITION_INJECT_RATE: float = float(
            os.getenv("DRAFTPROOF_TRANSITION_RATE", d.get("transition_inject_rate", 0.25))
        )
        self.WORD_REORDER_RATE: float = float(
            os.getenv("DRAFTPROOF_REORDER_RATE", d.get("word_reorder_rate", 0.20))
        )
        self.NOMINALIZATION_RATE: float = float(
            os.getenv("DRAFTPROOF_NOMINAL_RATE", d.get("nominalization_rate", 0.20))
        )
        self.APPOSITIVE_RATE: float = float(
            os.getenv("DRAFTPROOF_APPOSITIVE_RATE", d.get("appositive_rate", 0.35))
        )
        self.DISCOURSE_ROTATE_RATE: float = float(
            os.getenv("DRAFTPROOF_DISCOURSE_RATE", d.get("discourse_rotate_rate", 0.50))
        )
        self.SUBJECT_COORDINATION_RATE: float = float(
            os.getenv("DRAFTPROOF_SUBJECT_COORD_RATE", d.get("subject_coordination_rate", 0.35))
        )

        # Citation & UI Settings
        self.INSERT_CITATIONS: str = str(d.get("insert_citations", "Off"))
        self.CITATION_COUNT: str = str(d.get("citation_count", "Auto"))
        self.DISCIPLINE: str = str(d.get("discipline", "Auto-Detect Field"))
        self.UI_FLAGS: Dict[str, Any] = raw_global.get("ui_flags", {})
        self.WHITELISTED_USERS: list[str] = list(raw_global.get("whitelisted_users", []))
        self.TRAFFIC_BALANCING: Dict[str, Any] = raw_global.get("traffic_balancing", {})

    def apply_intensity(self, slider_value: float) -> None:
        """Scale all stage fire rates proportionally to the non-linear slider intensity."""
        self.INTENSITY = float(slider_value)
        eff = compute_effective_aggressiveness(slider_value, self.CURVE_EXPONENT)
        self.SYNONYM_AGGRESSIVENESS = eff
        scale = max(0.15, min(1.8, eff / 0.65))
        self.VOICE_TRANSFORM_RATE = min(0.95, round(0.30 * scale, 3))
        self.SENTENCE_FUSION_RATE = min(0.90, round(0.25 * scale, 3))
        self.TRANSITION_INJECT_RATE = min(0.90, round(0.25 * scale, 3))
        self.WORD_REORDER_RATE = min(0.85, round(0.20 * scale, 3))
        self.NOMINALIZATION_RATE = min(0.85, round(0.20 * scale, 3))
        self.APPOSITIVE_RATE = min(0.85, round(0.35 * scale, 3))
        self.DISCOURSE_ROTATE_RATE = min(0.95, round(0.50 * scale, 3))
        self.SUBJECT_COORDINATION_RATE = min(0.90, round(0.35 * scale, 3))


class AutoConfigNamespace(ConfigNamespace):
    """Zero-config namespace initialized from defaults and environment variables."""

    def __init__(self, input_dir: Optional[str] = None, output_dir: Optional[str] = None) -> None:
        super().__init__({})
        self.INPUT_DIR = input_dir or "paper_input"
        self.OUTPUT_DIR = output_dir or "paper_output"


def load_config_json(path: Optional[str | Path] = None) -> ConfigNamespace:
    """Load a ConfigNamespace from a JSON file path or global defaults."""
    if path and Path(path).exists():
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return ConfigNamespace(data)
    return ConfigNamespace({})


def auto_configure_project(
    input_dir: Optional[str] = None, output_dir: Optional[str] = None
) -> AutoConfigNamespace:
    """Automatically configure a project directory without manual JSON setup."""
    return AutoConfigNamespace(input_dir=input_dir, output_dir=output_dir)
