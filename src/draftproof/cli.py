"""Command-Line Interface Orchestrator (`src/draftproof/cli.py`).

Implements all flags specified in `GodGuide.md` Section 6:
- `--dry-run`: Preview changes without writing output files
- `--verbose`: Print detailed per-line modification logs during processing
- `--disable-stages`: Comma-separated stages to disable (`voice,fusion,transition,reorder,nominal,appositive,discourse`)
- `--max-aggressiveness`: Override all fire rates to maximum (0.95) for maximum similarity reduction
- Plus `--input`, `--output`, `--preset`, `--intensity`, `--citations`
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from draftproof.ai_detector import analyze_ai_signals, compare_documents_winnowing
from draftproof.config import auto_configure_project, load_config_json
from draftproof.core.citation_engine import CitationEngine
from draftproof.core.modifier import TextModifier
from draftproof.core.parser import parse_latex_zones


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="draftproof",
        description="DraftProof v2.0.0 — 100% Programmatic, Zero-AI Plagiarism & AI Footprint Removal Engine",
    )
    parser.add_argument(
        "-i", "--input", type=str, default="", help="Input file (.tex, .txt, .md) or directory"
    )
    parser.add_argument(
        "-o", "--output", type=str, default="", help="Output file or directory"
    )
    parser.add_argument(
        "--config", type=str, default="", help="Path to custom JSON configuration file"
    )
    parser.add_argument(
        "--preset",
        type=str,
        default="conversational",
        choices=["conversational", "academic", "technical"],
        help="Style preset (conversational, academic, technical)",
    )
    parser.add_argument(
        "--intensity", type=float, default=75.0, help="Humanizing intensity (0-100)"
    )
    parser.add_argument(
        "--citations",
        type=str,
        default="Off",
        help="Citation style to inject: Off, IEEE, APA, LaTeX",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing output files",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed per-line modification logs during processing",
    )
    parser.add_argument(
        "--disable-stages",
        type=str,
        default="",
        help="Comma-separated stages to disable: voice,fusion,transition,reorder,nominal,appositive,discourse",
    )
    parser.add_argument(
        "--max-aggressiveness",
        action="store_true",
        help="Override all fire rates to maximum (0.95) for maximum similarity reduction",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    print("═" * 72)
    print("  DRAFTPROOF v2.0.0 — ZERO-AI PLAGIARISM & WATERMARK REMOVAL ENGINE")
    print("═" * 72)

    print("\n[1/7] Loading configuration & decoupled rule repositories...")
    config = load_config_json(args.config) if args.config else auto_configure_project()
    config.STYLE_PRESET = args.preset
    config.apply_intensity(args.intensity)
    config.INSERT_CITATIONS = args.citations

    if args.disable_stages:
        stage_map = {
            "voice": "ENABLE_VOICE_TRANSFORM",
            "fusion": "ENABLE_SENTENCE_FUSION",
            "transition": "ENABLE_TRANSITION_INJECT",
            "reorder": "ENABLE_WORD_REORDER",
            "nominal": "ENABLE_NOMINALIZATION",
            "appositive": "ENABLE_APPOSITIVE",
            "discourse": "ENABLE_DISCOURSE_ROTATE",
        }
        for stage in args.disable_stages.split(","):
            stage = stage.strip().lower()
            if stage in stage_map:
                setattr(config, stage_map[stage], False)
                print(f"  [Disabled] {stage} transformation stage")

    if args.max_aggressiveness:
        config.SYNONYM_AGGRESSIVENESS = 0.95
        config.VOICE_TRANSFORM_RATE = 0.90
        config.SENTENCE_FUSION_RATE = 0.80
        config.TRANSITION_INJECT_RATE = 0.80
        config.WORD_REORDER_RATE = 0.75
        config.NOMINALIZATION_RATE = 0.70
        config.APPOSITIVE_RATE = 0.85
        config.DISCOURSE_ROTATE_RATE = 0.95
        print("  [MAX AGGRESSIVENESS] All fire rates set to maximum")

    print("\n[2/7] Resolving input source...")
    sample_default = (
        "In conclusion, it is important to delve into the comprehensive tapestry of modern neural networks. "
        "This study plays a pivotal role in illustrating that artificial intelligence stands as a testament "
        "to human innovation. Furthermore, the interplay between stochastic optimization and computational "
        "scalability provides a robust framework for subsequent empirical inquiries."
    )
    input_path = Path(args.input) if args.input else None
    if input_path and input_path.is_file():
        source_text = input_path.read_text(encoding="utf-8")
        print(f"  Loaded input file: {input_path} ({len(source_text)} chars)")
    else:
        source_text = sample_default
        print("  Using built-in benchmark sample paragraph.")

    print("\n[3/7] Zoning document & masking protected LaTeX/math tokens...")
    zones = parse_latex_zones(source_text)
    prose_zones = [z for z in zones if z["type"] == "PROSE"]
    print(f"  Total lines: {len(zones)} | Prose zones: {len(prose_zones)}")

    print("\n[4/7] Executing 19-stage deterministic transformation pipeline...")
    modifier = TextModifier(config=config)
    out_lines: List[str] = []
    for i, zone in enumerate(zones):
        line = str(zone["text"])
        if zone["type"] != "PROSE":
            out_lines.append(line)
            continue
        trailing_nl = line[len(line.rstrip("\r\n")) :]
        core = line.rstrip("\r\n")
        next_ctx = (
            [str(zones[i + 1]["text"]).strip()]
            if i + 1 < len(zones) and zones[i + 1]["type"] == "PROSE"
            else None
        )
        modified = modifier.modify_line(
            core, context_lines=next_ctx, section_name=str(zone.get("section", "body"))
        )
        if args.verbose and modified != core:
            print(f"    L{int(zone['idx']) + 1}: {core.strip()[:70]}...")
            print(f"       → {modified.strip()[:70]}...")
        out_lines.append(modified + trailing_nl)

    output_text = "".join(out_lines)
    if config.INSERT_CITATIONS.lower() != "off":
        c_engine = CitationEngine()
        c_res = c_engine.insert_citations(output_text, style=config.INSERT_CITATIONS)
        output_text = c_res.cited_text
        modifier.citation_insert_count += c_res.citations_inserted

    print(f"  AI tells scrubbed:     {modifier.ai_tells_scrubbed_count}")
    print(f"  Zero-width purged:     {modifier.zero_width_purged_count}")
    print(f"  Phrase rewrites:       {modifier.phrase_rewrite_count}")
    print(f"  Synonym swaps:         {modifier.synonym_swap_count}")
    print(f"  Clause reorders:       {modifier.clause_reorder_count}")
    print(f"  Determiner swaps:      {modifier.determiner_swap_count}")
    print(f"  Sentence splits:       {modifier.sentence_split_count}")
    print(f"  Hedge insertions:      {modifier.hedge_insert_count}")
    print(f"  N-gram chain breaks:   {modifier.ngram_break_count}")
    print(f"  Voice transforms:      {modifier.voice_transform_count}")
    print(f"  Sentence fusions:      {modifier.sentence_fusion_count}")
    print(f"  Transition injections: {modifier.transition_inject_count}")
    print(f"  Clause word reorders:  {modifier.clause_word_reorder_count}")
    print(f"  Nominalizations:       {modifier.nominalization_count}")
    print(f"  Appositive injections: {modifier.appositive_count}")
    print(f"  Discourse rotations:   {modifier.discourse_rotate_count}")
    print(f"  Subject coordinations: {modifier.subject_coordination_count}")

    total_transforms = (
        modifier.ai_tells_scrubbed_count
        + modifier.zero_width_purged_count
        + modifier.phrase_rewrite_count
        + modifier.synonym_swap_count
        + modifier.clause_reorder_count
        + modifier.determiner_swap_count
        + modifier.sentence_split_count
        + modifier.hedge_insert_count
        + modifier.ngram_break_count
        + modifier.voice_transform_count
        + modifier.sentence_fusion_count
        + modifier.transition_inject_count
        + modifier.clause_word_reorder_count
        + modifier.nominalization_count
        + modifier.appositive_count
        + modifier.discourse_rotate_count
        + modifier.subject_coordination_count
        + modifier.citation_insert_count
    )

    print("\n[5/7] Running Winnowing K-Gram Audit & ZipPy Perplexity Verification...")
    before_ai = analyze_ai_signals(source_text)
    after_ai = analyze_ai_signals(output_text)
    sim_rep = compare_documents_winnowing(source_text, output_text)
    print(
        f"  AI Detection Risk:     {before_ai.overall_ai_probability:.1f}% → {after_ai.overall_ai_probability:.1f}%"
    )
    print(
        f"  Winnowing Similarity:  {sim_rep.combined_similarity_pct:.1f}% (8-word matches: {sim_rep.guaranteed_8word_matches})"
    )

    print("\n[6/7] Writing output artifacts...")
    if args.dry_run:
        print("  DRY RUN — no files written")
    elif args.output:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(output_text, encoding="utf-8")
        print(f"  Wrote humanized output to: {out_p}")
    else:
        print(f"\n  Output Preview:\n  {output_text}")

    print("\n[7/7] SUMMARY")
    print(f"  Total transformations applied: {total_transforms}")
    print("═" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
