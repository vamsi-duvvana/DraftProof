"""Empirical Voice Matching Engine (v2.0.0).

Analyzes a user's reference writing sample (.txt, .md, .tex, .docx) to extract their
authentic stylometric fingerprint and calibrate the transformation pipeline.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from draftproof.config import ConfigNamespace


@dataclass
class VoiceProfile:
    """Stylometric fingerprint extracted from a user's writing sample."""

    sample_word_count: int
    sentence_count: int
    mean_sentence_length: float
    sentence_length_std: float
    burstiness_index: float
    contraction_rate: float
    type_token_ratio: float
    avg_word_length: float
    comma_per_sentence: float
    semicolon_per_sentence: float
    recommended_preset: str
    recommended_intensity: int
    recommended_fusion_rate: float
    recommended_split_enable: bool
    recommended_voice_rate: float
    recommended_discourse_rate: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_CONTRACTIONS_RE = re.compile(
    r"\b(?:don't|doesn't|didn't|won't|wouldn't|can't|couldn't|shouldn't|isn't|aren't|wasn't|weren't|haven't|hasn't|hadn't|it's|that's|there's|we're|they're|you're|I'm|I've|we've|they've|I'll|we'll)\b",
    re.IGNORECASE,
)


def analyze_voice_sample(text: str) -> VoiceProfile:
    """Extract stylometric parameters from a user writing sample."""
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", cleaned)
        if s.strip() and len(re.findall(r"\b\w+\b", s)) >= 2
    ]
    words = re.findall(r"\b[a-zA-Z']+\b", cleaned)
    total_words = len(words)
    if not sentences or total_words == 0:
        return VoiceProfile(
            sample_word_count=0,
            sentence_count=0,
            mean_sentence_length=18.0,
            sentence_length_std=7.5,
            burstiness_index=0.42,
            contraction_rate=0.0,
            type_token_ratio=0.65,
            avg_word_length=5.1,
            comma_per_sentence=1.2,
            semicolon_per_sentence=0.05,
            recommended_preset="conversational",
            recommended_intensity=75,
            recommended_fusion_rate=0.25,
            recommended_split_enable=True,
            recommended_voice_rate=0.30,
            recommended_discourse_rate=0.50,
        )

    lengths: List[int] = [len(re.findall(r"\b\w+\b", s)) for s in sentences]
    n_sent = len(lengths)
    mean_len = sum(lengths) / n_sent
    variance = sum((L - mean_len) ** 2 for L in lengths) / max(1, n_sent)
    std_len = math.sqrt(variance)
    burstiness = std_len / max(1.0, mean_len)

    contractions = len(_CONTRACTIONS_RE.findall(cleaned))
    contraction_rate = contractions / max(1, total_words)

    unique_words = len({w.lower() for w in words})
    ttr = unique_words / max(1, total_words)
    avg_word_len = sum(len(w) for w in words) / max(1, total_words)

    commas = cleaned.count(",") / n_sent
    semicolons = cleaned.count(";") / n_sent

    # Infer preset & stage calibration from user's natural writing style
    is_academic = avg_word_len >= 5.35 and contraction_rate < 0.005
    preset = "academic" if is_academic else "conversational"

    # If user writes long sentences (>22 words), favor fusion over splitting; if short (<15), favor splitting
    fusion_rate = min(0.65, max(0.10, round((mean_len - 12.0) / 40.0, 2)))
    split_enable = mean_len < 26.0
    voice_rate = min(0.55, max(0.15, round(0.20 + (avg_word_len - 4.5) * 0.15, 2)))
    discourse_rate = min(0.75, max(0.25, round(0.35 + commas * 0.12, 2)))
    intensity = int(min(90, max(55, round(65 + burstiness * 25))))

    return VoiceProfile(
        sample_word_count=total_words,
        sentence_count=n_sent,
        mean_sentence_length=round(mean_len, 2),
        sentence_length_std=round(std_len, 2),
        burstiness_index=round(burstiness, 3),
        contraction_rate=round(contraction_rate, 4),
        type_token_ratio=round(ttr, 3),
        avg_word_length=round(avg_word_len, 2),
        comma_per_sentence=round(commas, 2),
        semicolon_per_sentence=round(semicolons, 2),
        recommended_preset=preset,
        recommended_intensity=intensity,
        recommended_fusion_rate=fusion_rate,
        recommended_split_enable=split_enable,
        recommended_voice_rate=voice_rate,
        recommended_discourse_rate=discourse_rate,
    )


def apply_voice_profile_to_config(profile: VoiceProfile, config: ConfigNamespace) -> ConfigNamespace:
    """Calibrate a ConfigNamespace in-place to mirror the user's empirical VoiceProfile."""
    config.STYLE_PRESET = profile.recommended_preset
    config.apply_intensity(profile.recommended_intensity)
    config.SENTENCE_FUSION_RATE = profile.recommended_fusion_rate
    config.ENABLE_SENTENCE_SPLIT = profile.recommended_split_enable
    config.VOICE_TRANSFORM_RATE = profile.recommended_voice_rate
    config.DISCOURSE_ROTATE_RATE = profile.recommended_discourse_rate
    return config
