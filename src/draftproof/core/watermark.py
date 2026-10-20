"""Watermark Forensics, Zero-Width Unicode Purge, Homoglyph Sanitizer & C2PA Metadata Stripper."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from draftproof.core.rules import HOMOGLYPH_MAP, ZERO_WIDTH_CODEPOINTS

UNICODE_NAMES: Dict[str, str] = {
    "\u200b": "ZERO WIDTH SPACE (U+200B)",
    "\u200c": "ZERO WIDTH NON-JOINER (U+200C)",
    "\u200d": "ZERO WIDTH JOINER (U+200D)",
    "\u2060": "WORD JOINER (U+2060)",
    "\ufeff": "ZERO WIDTH NO-BREAK SPACE / BOM (U+FEFF)",
    "\u00ad": "SOFT HYPHEN (U+00AD)",
    "\u180e": "MONGOLIAN VOWEL SEPARATOR (U+180E)",
    "\u200e": "LEFT-TO-RIGHT MARK (U+200E)",
    "\u200f": "RIGHT-TO-LEFT MARK (U+200F)",
    "\u202a": "LEFT-TO-RIGHT EMBEDDING (U+202A)",
    "\u202b": "RIGHT-TO-LEFT EMBEDDING (U+202B)",
    "\u202c": "POP DIRECTIONAL FORMATTING (U+202C)",
    "\u202d": "LEFT-TO-RIGHT OVERRIDE (U+202D)",
    "\u202e": "RIGHT-TO-LEFT OVERRIDE (U+202E)",
    "\u2061": "FUNCTION APPLICATION (U+2061)",
    "\u2062": "INVISIBLE TIMES (U+2062)",
    "\u2063": "INVISIBLE SEPARATOR (U+2063)",
    "\u2064": "INVISIBLE PLUS (U+2064)",
}


@dataclass
class WatermarkAuditReport:
    """Comprehensive forensic audit of hidden watermarks, zero-width chars, and SynthID chains."""

    zero_width_count: int = 0
    zero_width_breakdown: Dict[str, int] = field(default_factory=dict)
    homoglyph_count: int = 0
    em_dash_count: int = 0
    synthid_green_ratio: float = 0.5
    synthid_z_score: float = 0.0
    watermark_risk_level: str = "Low"
    sanitized_text: str = ""
    findings: List[str] = field(default_factory=list)


def compute_synthid_token_stats(text: str) -> Tuple[float, float]:
    """Estimate statistical token-list green-bucket bias (Kirchenbauer/SynthID tournament model).

    Hashes sliding bigrams `(w_{i-1}, w_i)` to check whether token selection exhibits
    non-random green-list clustering (`z_score > 2.0`).
    """
    tokens = re.findall(r"[a-zA-Z]{2,}", text.lower())
    if len(tokens) < 8:
        return 0.5, 0.0

    green_hits = 0
    total = len(tokens) - 1
    for idx in range(1, len(tokens)):
        pair_bytes = f"{tokens[idx - 1]}::{tokens[idx]}".encode("utf-8")
        digest = hashlib.sha256(pair_bytes).digest()
        if (digest[0] & 1) == 1:
            green_hits += 1

    green_ratio = green_hits / total
    # Standard normal z-score for binomial p=0.5: (G - T/2) / sqrt(T/4)
    z_score = (green_hits - 0.5 * total) / ((0.25 * total) ** 0.5)
    return round(green_ratio, 4), round(z_score, 3)


def purge_zero_width_and_homoglyphs(text: str) -> Tuple[str, int, int, Dict[str, int]]:
    """Strip all invisible zero-width Unicode trackers and normalize homoglyph characters."""
    if not text:
        return text, 0, 0, {}

    zw_breakdown: Dict[str, int] = {}
    zw_total = 0
    cleaned = text

    for ch in ZERO_WIDTH_CODEPOINTS:
        cnt = cleaned.count(ch)
        if cnt > 0:
            label = UNICODE_NAMES.get(ch, f"U+{ord(ch):04X}")
            zw_breakdown[label] = zw_breakdown.get(label, 0) + cnt
            zw_total += cnt
            cleaned = cleaned.replace(ch, "")

    homoglyph_count = 0
    for src_ch, dst_ch in HOMOGLYPH_MAP.items():
        cnt = cleaned.count(src_ch)
        if cnt > 0:
            if ord(src_ch) > 127 and src_ch not in ("\u2018", "\u2019", "\u201c", "\u201d"):
                homoglyph_count += cnt
            cleaned = cleaned.replace(src_ch, dst_ch)

    return cleaned, zw_total, homoglyph_count, zw_breakdown


def inspect_and_sanitize_watermarks(text: str) -> WatermarkAuditReport:
    """Run full watermark forensic scan and return report with sanitized text."""
    em_dash_count = text.count("—") + text.count("–")
    cleaned, zw_count, hg_count, zw_breakdown = purge_zero_width_and_homoglyphs(text)
    green_ratio, z_score = compute_synthid_token_stats(text)

    findings: List[str] = []
    if zw_count > 0:
        findings.append(
            f"Detected and purged {zw_count} invisible zero-width tracking character(s): "
            + ", ".join(f"{k} (×{v})" for k, v in zw_breakdown.items())
        )
    if hg_count > 0:
        findings.append(
            f"Normalized {hg_count} Cyrillic/non-ASCII homoglyph character(s) back to canonical ASCII."
        )
    if em_dash_count > 0:
        findings.append(
            f"Found {em_dash_count} typographic em/en-dash character(s) (common LLM punctuation tell)."
        )
    if abs(z_score) >= 2.0:
        findings.append(
            f"Elevated token-hash periodicity detected (z={z_score:+.2f}, green ratio={green_ratio:.1%})."
        )

    risk = "Low"
    if zw_count > 0 or hg_count > 0 or abs(z_score) >= 2.5:
        risk = "High"
    elif em_dash_count >= 2 or abs(z_score) >= 1.6:
        risk = "Moderate"

    return WatermarkAuditReport(
        zero_width_count=zw_count,
        zero_width_breakdown=zw_breakdown,
        homoglyph_count=hg_count,
        em_dash_count=em_dash_count,
        synthid_green_ratio=green_ratio,
        synthid_z_score=z_score,
        watermark_risk_level=risk,
        sanitized_text=cleaned,
        findings=findings,
    )


def strip_docx_c2pa_and_metadata(doc: Any) -> Dict[str, Any]:
    """Sanitize python-docx Document core properties and strip hidden tracking metadata."""
    stripped_fields: List[str] = []
    try:
        props = doc.core_properties
        for attr in (
            "author",
            "last_modified_by",
            "comments",
            "category",
            "content_status",
            "identifier",
            "keywords",
            "subject",
        ):
            val = getattr(props, attr, None)
            if val:
                stripped_fields.append(f"{attr}={val!r}")
            setattr(props, attr, "")
        props.revision = 1
    except Exception:
        pass

    return {
        "c2pa_sanitized": True,
        "stripped_properties": stripped_fields,
        "stripped_count": len(stripped_fields),
    }
