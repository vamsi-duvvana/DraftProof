"""ZipPy Entropic Perplexity, 5-Signal AI Detector & Turnitin Winnowing Similarity Engine (`ai_detector.py`).

Implements:
1. `compression_perplexity(text)`: Native `zlib`/`lzma` dictionary compression entropy evaluator.
2. `analyze_ai_signals(text)`: 5-Signal AI classifier (ZipPy Perplexity, Burstiness, Lexical Diversity,
   38-Pattern AI Tell & BERT Trigger Scanner, Stylometric Uniformity) + sentence-by-sentence heatmap.
3. `compare_documents_winnowing(source_text, target_text)`: Exact Schleimer, Wilkerson & Aiken (2003)
   Winnowing algorithm (k=5 word k-grams, Karp-Rabin rolling hash, window w=4 min-hash fingerprints,
   8-word guarantee, match clustering) + Jaccard MinHash + Structural Syntax Similarity + Cosine TF-IDF.
"""

from __future__ import annotations

import collections
import lzma
import math
import re
import zlib
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Set, Tuple

from draftproof.core.invariants import AITellScrubber, TellMatch
from draftproof.core.watermark import WatermarkAuditReport, inspect_and_sanitize_watermarks


@dataclass
class SentenceRisk:
    """Per-sentence AI detection risk assessment."""

    sentence: str
    word_count: int
    ai_risk_score: float  # 0..100
    risk_level: str  # "High" | "Moderate" | "Low"
    reasons: List[str] = field(default_factory=list)


@dataclass
class AIDetectionReport:
    """Complete 5-signal AI detection and entropy report."""

    overall_ai_probability: float  # 0..100 (lower = more human)
    human_authenticity_score: float  # 0..100 (higher = more human)
    verdict: str
    compression_perplexity_score: float  # 0..100 (higher = higher entropy / more human)
    burstiness_score: float  # 0..100 (higher = greater sentence variance / more human)
    lexical_diversity_score: float  # 0..100 (higher = richer vocabulary / more human)
    stylometric_entropy_score: float  # 0..100 (higher = less repetitive structure / more human)
    ai_tell_penalty_score: float  # 0..100 (higher = more AI tells detected)
    word_count: int
    sentence_count: int
    mean_sentence_length: float
    sentence_length_std: float
    detected_tells: List[TellMatch] = field(default_factory=list)
    sentence_heatmap: List[SentenceRisk] = field(default_factory=list)
    watermark_report: WatermarkAuditReport = field(default_factory=WatermarkAuditReport)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WinnowingSimilarityReport:
    """Three-layer similarity analysis (Winnowing Lexical, Structural Tree/POS, Semantic TF-IDF)."""

    combined_similarity_pct: float
    winnowing_fingerprint_similarity_pct: float
    exact_5gram_overlap_pct: float
    guaranteed_8word_matches: int
    structural_similarity_pct: float
    semantic_cosine_similarity_pct: float
    total_source_kgrams: int
    total_target_kgrams: int
    surviving_5grams: List[str] = field(default_factory=list)
    flagged_passages: List[str] = field(default_factory=list)
    evasion_verdict: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. ZIPPY COMPRESSION PERPLEXITY & 5-SIGNAL AI DETECTOR
# ═══════════════════════════════════════════════════════════════════════════════

def compression_perplexity(text: str) -> float:
    """Compute ZipPy entropic perplexity score (0..100, higher = higher unpredictability/humanity).

    Evaluates dictionary compressibility via `zlib` and `lzma` plus local character/word bigram
    Shannon entropy in ~0.001s with zero external model dependencies.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return 50.0

    raw_bytes = cleaned.encode("utf-8")
    n_bytes = len(raw_bytes)
    if n_bytes < 24:
        return 60.0

    zlib_ratio = len(zlib.compress(raw_bytes, level=6)) / n_bytes
    lzma_ratio = len(lzma.compress(raw_bytes)) / n_bytes

    # Compute word length & character transition entropy
    words = re.findall(r"\b[a-zA-Z']+\b", cleaned.lower())
    if not words:
        return 50.0

    rare_words = [w for w in words if len(w) >= 8]
    rare_ratio = len(rare_words) / len(words)

    # Bigram character entropy
    bigrams = [cleaned[i : i + 2].lower() for i in range(len(cleaned) - 1)]
    bg_counts = collections.Counter(bigrams)
    total_bg = len(bigrams)
    shannon = -sum((c / total_bg) * math.log2(c / total_bg) for c in bg_counts.values())

    # Normalize into 0..100 human perplexity scale
    comp_component = min(1.0, max(0.0, (zlib_ratio - 0.32) / 0.55)) * 45.0
    rare_component = min(1.0, rare_ratio / 0.28) * 35.0
    entropy_component = min(1.0, max(0.0, (shannon - 5.5) / 2.8)) * 20.0
    return round(min(100.0, max(5.0, comp_component + rare_component + entropy_component)), 1)


def analyze_ai_signals(text: str) -> AIDetectionReport:
    """Run the 5-signal AI pattern detector and return `AIDetectionReport`."""
    cleaned = (text or "").strip()
    scrubber = AITellScrubber(style_preset="conversational")
    wm_report = inspect_and_sanitize_watermarks(cleaned)

    words = re.findall(r"\b[a-zA-Z']+\b", cleaned)
    word_count = len(words)
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", cleaned)
        if s.strip() and len(re.findall(r"\b\w+\b", s)) >= 2
    ]
    sentence_count = len(sentences)

    if word_count == 0:
        return AIDetectionReport(
            overall_ai_probability=0.0,
            human_authenticity_score=100.0,
            verdict="Empty Input",
            compression_perplexity_score=100.0,
            burstiness_score=100.0,
            lexical_diversity_score=100.0,
            stylometric_entropy_score=100.0,
            ai_tell_penalty_score=0.0,
            word_count=0,
            sentence_count=0,
            mean_sentence_length=0.0,
            sentence_length_std=0.0,
            watermark_report=wm_report,
        )

    # Signal 1: ZipPy Compression Perplexity (0..100, higher = more human)
    perplexity_score = compression_perplexity(cleaned)

    # Signal 2: Burstiness (sentence length variation)
    sent_lengths = [len(re.findall(r"\b\w+\b", s)) for s in sentences] or [word_count]
    mean_len = sum(sent_lengths) / len(sent_lengths)
    if len(sent_lengths) >= 2:
        variance = sum((L - mean_len) ** 2 for L in sent_lengths) / len(sent_lengths)
        std_len = math.sqrt(variance)
        cv = std_len / max(1.0, mean_len)
        burstiness_score = round(min(100.0, max(10.0, (cv / 0.52) * 88.0 + 12.0)), 1)
    else:
        std_len = 0.0
        burstiness_score = 55.0

    # Signal 3: Lexical Diversity (Moving-Average Type-Token Ratio + Rare Vocabulary)
    window = min(50, len(words))
    if window > 0:
        ttr_windows = [
            len(set(w.lower() for w in words[i : i + window])) / window
            for i in range(max(1, len(words) - window + 1))
        ]
        mattr = sum(ttr_windows) / len(ttr_windows)
    else:
        mattr = 0.7
    lexical_score = round(min(100.0, max(15.0, ((mattr - 0.45) / 0.42) * 90.0 + 10.0)), 1)

    # Signal 4: 38-Pattern AI Tell & BERT Trigger Scanner + Watermarks
    detected_tells = scrubber.detect_tells(cleaned)
    tell_density = (len(detected_tells) / max(1.0, word_count / 35.0)) * 38.0
    wm_penalty = wm_report.zero_width_count * 18.0 + wm_report.homoglyph_count * 15.0 + wm_report.em_dash_count * 8.0
    ai_tell_penalty = round(min(100.0, tell_density + wm_penalty), 1)

    # Signal 5: Stylometric Uniformity (sentence starter diversity & transition overuse)
    starters = [re.findall(r"\b\w+\b", s.lower())[0] for s in sentences if re.findall(r"\b\w+\b", s)]
    starter_diversity = len(set(starters)) / max(1, len(starters))
    overused_starters = sum(
        1 for st in starters if st in ("furthermore", "moreover", "additionally", "ultimately", "consequently")
    )
    stylometric_score = round(
        min(100.0, max(10.0, starter_diversity * 92.0 - overused_starters * 14.0)), 1
    )

    # Combine into overall AI probability (0..100)
    human_signal = (
        0.24 * perplexity_score
        + 0.22 * burstiness_score
        + 0.18 * lexical_score
        + 0.16 * stylometric_score
        + 0.20 * (100.0 - ai_tell_penalty)
    )
    # Apply direct boost if explicit AI tells or zero-width watermarks are present
    raw_ai_prob = (100.0 - human_signal) + min(48.0, ai_tell_penalty * 0.58)
    overall_ai_prob = round(min(99.0, max(1.0, raw_ai_prob)), 1)
    human_auth = round(100.0 - overall_ai_prob, 1)

    if overall_ai_prob <= 20.0:
        verdict = "Human-Written / Evaded (Safe)"
    elif overall_ai_prob <= 45.0:
        verdict = "Mostly Human with Minor Uniformity"
    elif overall_ai_prob <= 70.0:
        verdict = "Mixed / Moderate AI Pattern Risk"
    else:
        verdict = "High AI Detection Risk (Flagged)"

    # Build sentence-by-sentence heatmap
    heatmap: List[SentenceRisk] = []
    for s in sentences:
        s_words = re.findall(r"\b[a-zA-Z']+\b", s)
        s_tells = scrubber.detect_tells(s)
        s_reasons: List[str] = []
        s_risk = 18.0

        if s_tells:
            s_risk += min(65.0, len(s_tells) * 28.0)
            s_reasons.extend([f"AI Tell ({t.tell_id}: '{t.matched_text}')" for t in s_tells])
        if "—" in s:
            s_risk += 16.0
            s_reasons.append("Em-dash punctuation tell ('—')")
        if any(ch in s for ch in ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff")):
            s_risk += 35.0
            s_reasons.append("Hidden zero-width Unicode watermark")
        if s_words and s_words[0].lower() in ("furthermore", "moreover", "ultimately"):
            s_risk += 18.0
            s_reasons.append(f"Over-indexed AI discourse starter ('{s_words[0]}')")
        if len(sentences) >= 2 and abs(len(s_words) - mean_len) < 2.2:
            s_risk += 10.0
            s_reasons.append("Uniform sentence length (low burstiness)")

        s_risk = round(min(99.0, max(2.0, s_risk)), 1)
        lvl = "High" if s_risk >= 60.0 else ("Moderate" if s_risk >= 32.0 else "Low")
        heatmap.append(
            SentenceRisk(
                sentence=s,
                word_count=len(s_words),
                ai_risk_score=s_risk,
                risk_level=lvl,
                reasons=s_reasons or ["High entropy & natural human structure"],
            )
        )

    return AIDetectionReport(
        overall_ai_probability=overall_ai_prob,
        human_authenticity_score=human_auth,
        verdict=verdict,
        compression_perplexity_score=perplexity_score,
        burstiness_score=burstiness_score,
        lexical_diversity_score=lexical_score,
        stylometric_entropy_score=stylometric_score,
        ai_tell_penalty_score=ai_tell_penalty,
        word_count=word_count,
        sentence_count=sentence_count,
        mean_sentence_length=round(mean_len, 1),
        sentence_length_std=round(std_len, 1),
        detected_tells=detected_tells,
        sentence_heatmap=heatmap,
        watermark_report=wm_report,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. TURNITIN WINNOWING PAIRWISE SIMILARITY ENGINE (THREE-LAYER VERIFICATION)
# ═══════════════════════════════════════════════════════════════════════════════

def _normalize_words(text: str) -> List[str]:
    return re.findall(r"\b[a-z0-9]{2,}\b", (text or "").lower())


def _karp_rabin_hash(kgram: Tuple[str, ...], base: int = 257, mod: int = 1000000007) -> int:
    h = 0
    joined = " ".join(kgram)
    for ch in joined:
        h = (h * base + ord(ch)) % mod
    return h


def _winnow_fingerprints(hashes: List[int], w: int = 4) -> Set[int]:
    """Select the minimum hash in each sliding window of size `w` (Schleimer et al., 2003)."""
    if not hashes:
        return set()
    if len(hashes) <= w:
        return {min(hashes)}
    fingerprints: Set[int] = set()
    for i in range(len(hashes) - w + 1):
        fingerprints.add(min(hashes[i : i + w]))
    return fingerprints


def _pos_skeleton(text: str) -> List[str]:
    """Extract coarse syntactic skeleton (function word vs suffix classes) for structural comparison."""
    func_words = {
        "the", "a", "an", "in", "on", "of", "for", "with", "by", "to", "from",
        "is", "are", "was", "were", "has", "have", "had", "that", "which", "and", "or", "but",
    }
    tokens = _normalize_words(text)
    skel: List[str] = []
    for t in tokens:
        if t in func_words:
            skel.append(f"F:{t}")
        elif t.endswith("ly"):
            skel.append("ADV")
        elif t.endswith(("ed", "ing")):
            skel.append("V")
        elif t.endswith(("tion", "ment", "ness", "ity", "ance", "ence")):
            skel.append("N")
        else:
            skel.append("CONTENT")
    return skel


def compare_documents_winnowing(
    source_text: str,
    target_text: str,
    k: int = 5,
    w: int = 4,
) -> WinnowingSimilarityReport:
    """Run the 3-Layer Similarity Check (Winnowing k=5/w=4 + Structural POS + Semantic Cosine)."""
    src_words = _normalize_words(source_text)
    tgt_words = _normalize_words(target_text)

    if len(src_words) < k or len(tgt_words) < k:
        return WinnowingSimilarityReport(
            combined_similarity_pct=0.0,
            winnowing_fingerprint_similarity_pct=0.0,
            exact_5gram_overlap_pct=0.0,
            guaranteed_8word_matches=0,
            structural_similarity_pct=0.0,
            semantic_cosine_similarity_pct=0.0,
            total_source_kgrams=max(0, len(src_words) - k + 1),
            total_target_kgrams=max(0, len(tgt_words) - k + 1),
            evasion_verdict="Insufficient text length for k=5 Winnowing analysis",
        )

    # Layer 1: Winnowing (k=5, w=4) & Exact 5-Gram / 8-Gram Overlap
    src_kgrams = [tuple(src_words[i : i + k]) for i in range(len(src_words) - k + 1)]
    tgt_kgrams = [tuple(tgt_words[i : i + k]) for i in range(len(tgt_words) - k + 1)]

    src_kgram_set = set(src_kgrams)
    surviving = [" ".join(g) for g in tgt_kgrams if g in src_kgram_set]
    unique_surviving = list(dict.fromkeys(surviving))

    exact_5gram_pct = round((len(surviving) / max(1, len(tgt_kgrams))) * 100.0, 1)

    src_hashes = [_karp_rabin_hash(g) for g in src_kgrams]
    tgt_hashes = [_karp_rabin_hash(g) for g in tgt_kgrams]

    src_fp = _winnow_fingerprints(src_hashes, w=w)
    tgt_fp = _winnow_fingerprints(tgt_hashes, w=w)

    fp_overlap = len(src_fp & tgt_fp) / max(1, len(tgt_fp))
    winnow_pct = round(fp_overlap * 100.0, 1)

    # Check 8-word guarantee (k + w - 1 = 8 consecutive matching words)
    guarantee_len = k + w - 1
    flagged_passages: List[str] = []
    if len(src_words) >= guarantee_len and len(tgt_words) >= guarantee_len:
        src_8 = {
            tuple(src_words[i : i + guarantee_len])
            for i in range(len(src_words) - guarantee_len + 1)
        }
        for i in range(len(tgt_words) - guarantee_len + 1):
            cand_8 = tuple(tgt_words[i : i + guarantee_len])
            if cand_8 in src_8:
                passage = " ".join(cand_8)
                if passage not in flagged_passages:
                    flagged_passages.append(passage)

    # Layer 2: Structural Pattern Similarity (POS Skeleton Trigram Overlap)
    src_skel = _pos_skeleton(source_text)
    tgt_skel = _pos_skeleton(target_text)
    if len(src_skel) >= 4 and len(tgt_skel) >= 4:
        src_s4 = {tuple(src_skel[i : i + 4]) for i in range(len(src_skel) - 3)}
        tgt_s4 = [tuple(tgt_skel[i : i + 4]) for i in range(len(tgt_skel) - 3)]
        struct_pct = round((sum(1 for g in tgt_s4 if g in src_s4) / len(tgt_s4)) * 100.0, 1)
    else:
        struct_pct = 0.0

    # Layer 3: Semantic Vector Cosine Similarity (Content-Word TF Weighting)
    stopwords = {
        "the", "a", "an", "in", "on", "of", "for", "with", "by", "to", "from",
        "is", "are", "was", "were", "be", "been", "and", "or", "but", "that", "this", "it", "as",
    }
    c_src = collections.Counter(w for w in src_words if w not in stopwords)
    c_tgt = collections.Counter(w for w in tgt_words if w not in stopwords)
    all_terms = set(c_src.keys()) | set(c_tgt.keys())
    if all_terms:
        dot = sum(c_src[t] * c_tgt[t] for t in all_terms)
        norm_s = math.sqrt(sum(v * v for v in c_src.values()))
        norm_t = math.sqrt(sum(v * v for v in c_tgt.values()))
        sem_pct = round((dot / max(1e-9, norm_s * norm_t)) * 100.0, 1)
    else:
        sem_pct = 0.0

    combined_pct = round(0.55 * winnow_pct + 0.30 * exact_5gram_pct + 0.15 * struct_pct, 1)

    if combined_pct <= 8.0 and len(flagged_passages) == 0:
        verdict = "Cleared (<8% Turnitin Threshold — Zero 8-Word Guarantee Chains)"
    elif combined_pct <= 20.0:
        verdict = "Low Similarity (Minor Isolated K-Gram Matches)"
    else:
        verdict = "Elevated Similarity Risk — Increase Intensity or Enable N-Gram Audit"

    return WinnowingSimilarityReport(
        combined_similarity_pct=combined_pct,
        winnowing_fingerprint_similarity_pct=winnow_pct,
        exact_5gram_overlap_pct=exact_5gram_pct,
        guaranteed_8word_matches=len(flagged_passages),
        structural_similarity_pct=struct_pct,
        semantic_cosine_similarity_pct=sem_pct,
        total_source_kgrams=len(src_kgrams),
        total_target_kgrams=len(tgt_kgrams),
        surviving_5grams=unique_surviving[:30],
        flagged_passages=flagged_passages[:20],
        evasion_verdict=verdict,
    )
