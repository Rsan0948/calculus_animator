#!/usr/bin/env python3
"""Generate before/after slide quality audits and training pairs."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.slide_highlighting import (  # noqa: E402
    build_informative_slide_highlights,
    build_legacy_slide_highlights,
)

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "as", "by", "is", "are", "was", "were",
    "be", "being", "been", "this", "that", "these", "those", "it", "its", "at", "from", "if", "then", "than", "so",
    "but", "into", "about", "over", "under", "not", "you", "your", "we", "our", "they", "their", "them", "he", "she",
    "his", "her", "can", "could", "should", "would", "will", "just", "very", "more", "most", "all", "any", "some",
    "each", "every", "also", "use", "using", "used", "let", "lets",
}

MATH_WORDS = {
    "function", "domain", "range", "slope", "intercept", "vertex", "parabola", "polynomial", "rational", "asymptote",
    "compose", "composition", "inverse", "exponential", "logarithm", "logarithmic", "natural", "sequence", "series",
    "arithmetic", "geometric", "limit", "derivative", "integral", "sin", "cos", "tan", "identity", "radian",
}

EXPLANATION_CUES = ("because", "means", "therefore", "if", "when", "important", "notice", "so that", "in other words")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_ws(text: str) -> str:
    return " ".join(str(text or "").split())


def _extract_tokens(text: str) -> List[str]:
    raw = re.findall(r"[a-zA-Z][a-zA-Z0-9]{1,}|[0-9]+", str(text or "").lower())
    return [t for t in raw if t not in STOPWORDS and (len(t) > 2 or t.isdigit())]


def _extract_math_tokens(text: str) -> List[str]:
    s = str(text or "").lower()
    found = set()
    for w in MATH_WORDS:
        if re.search(rf"\b{re.escape(w)}\b", s):
            found.add(w)
    for pat in (
        r"[a-z]\s*\^\s*\(?[a-z0-9+\-]+\)?",
        r"\b[a-z0-9]+\s*/\s*[a-z0-9]+\b",
        r"\\frac|\\lim|\\int|\\sin|\\cos|\\tan|sqrt|log|ln",
    ):
        for m in re.findall(pat, s):
            found.add(m.strip())
    return sorted(found)


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _evaluate(notes_blocks: List[Dict], highlights: List[Dict]) -> Dict:
    notes_text = "\n\n".join(_normalize_ws(b.get("text") or "") for b in notes_blocks if _normalize_ws(b.get("text") or ""))
    hl_text = " ".join(_normalize_ws(h.get("text") or "") for h in highlights if _normalize_ws(h.get("text") or ""))

    notes_tokens = _extract_tokens(notes_text)
    hl_tokens = _extract_tokens(hl_text)
    notes_set = set(notes_tokens)
    hl_set = set(hl_tokens)
    overlap = len(notes_set & hl_set)
    coverage = overlap / max(1, len(notes_set))

    notes_math = set(_extract_math_tokens(notes_text))
    hl_math = set(_extract_math_tokens(hl_text))
    math_coverage = 1.0 if not notes_math else len(notes_math & hl_math) / len(notes_math)

    chars = len(hl_text)
    target_min, target_max = 260, 620
    if chars < target_min:
        density = max(0.0, chars / target_min)
    elif chars <= target_max:
        density = 1.0
    else:
        density = max(0.0, 1.0 - ((chars - target_max) / target_max))

    items = [h.get("text", "") for h in highlights if _normalize_ws(h.get("text") or "")]
    words_per_item = []
    explanation_hits = 0
    for item in items:
        words = _extract_tokens(item)
        if words:
            words_per_item.append(len(words))
        low = item.lower()
        if any(cue in low for cue in EXPLANATION_CUES):
            explanation_hits += 1
    avg_words = sum(words_per_item) / max(1, len(words_per_item))
    clarity = 1.0
    if avg_words < 10:
        clarity -= 0.25
    if avg_words > 34:
        clarity -= 0.2
    if len(items) < 3:
        clarity -= 0.25
    if explanation_hits == 0:
        clarity -= 0.15
    clarity = max(0.0, min(1.0, clarity))

    learnability = max(0.0, min(1.0, 0.45 * coverage + 0.2 * math_coverage + 0.2 * clarity + 0.15 * density))
    score = round((0.36 * coverage + 0.24 * math_coverage + 0.2 * clarity + 0.2 * density) * 100, 1)

    note_counts = Counter(notes_tokens)
    missing = [t for t, _ in note_counts.most_common(24) if t not in hl_set][:10]
    captured = [t for t, _ in note_counts.most_common(24) if t in hl_set][:10]

    issues = []
    if coverage < 0.55:
        issues.append("low concept coverage")
    if math_coverage < 0.6:
        issues.append("missing math/formula detail")
    if density < 0.75:
        if chars < target_min:
            issues.append("overly concise")
        else:
            issues.append("too dense for slide constraints")
    if clarity < 0.75:
        issues.append("clarity/teaching flow needs improvement")
    if not issues:
        issues.append("balanced and instruction-ready")

    return {
        "score": score,
        "grade": _grade(score),
        "coverage": round(coverage, 3),
        "math_coverage": round(math_coverage, 3),
        "density_fit": round(density, 3),
        "clarity": round(clarity, 3),
        "learnability": round(learnability, 3),
        "highlight_chars": chars,
        "highlight_count": len(items),
        "captured_keywords": captured,
        "missing_keywords": missing,
        "issues": issues,
    }


def _review_text(kind: str, metrics: Dict) -> str:
    tone = "Before rewrite" if kind == "before" else "After rewrite"
    parts = [f"{tone}: grade {metrics['grade']} ({metrics['score']}/100)."]
    if metrics["coverage"] < 0.55:
        parts.append("Slide misses key note concepts and underspecifies explanations.")
    elif metrics["coverage"] < 0.72:
        parts.append("Concept coverage is partial; some key ideas are still compressed.")
    else:
        parts.append("Concept coverage is strong for slide-level teaching.")

    if metrics["math_coverage"] < 0.6:
        parts.append("Important math terms/formulas are missing or weakly represented.")
    elif metrics["math_coverage"] >= 0.85:
        parts.append("Math detail fidelity to notes is strong.")

    if metrics["density_fit"] < 0.75:
        if metrics["highlight_chars"] < 260:
            parts.append("Content is too concise to be independently instructional.")
        else:
            parts.append("Content is too dense for comfortable slide consumption.")

    if metrics["clarity"] < 0.75:
        parts.append("Flow and explanatory scaffolding need improvement.")
    else:
        parts.append("Flow is readable and supports learning without mandatory notes.")
    return " ".join(parts)


def _load_curriculum(root: Path, content_file: str, curriculum_file: str) -> Dict:
    content_path = root / content_file
    default_path = root / curriculum_file
    default = {"pathways": []}
    if default_path.exists():
        default = json.loads(default_path.read_text(encoding="utf-8"))
    if content_path.exists():
        data = json.loads(content_path.read_text(encoding="utf-8"))
        pathway = data.get("pathway")
        if isinstance(pathway, dict):
            rest = [p for p in (default.get("pathways") or []) if p.get("id") != pathway.get("id")]
            return {"pathways": [pathway] + rest}
    return default


def _iter_slides(curriculum: Dict) -> Iterable[Tuple[Dict, Dict, Dict]]:
    for pathway in curriculum.get("pathways") or []:
        for chapter in pathway.get("chapters") or []:
            for slide in chapter.get("slides") or []:
                yield pathway, chapter, slide


def _write_markdown(path: Path, report: Dict):
    slides = report["slides"]
    summary = report["summary"]
    lines = []
    lines.append("# Slide Quality Audit")
    lines.append("")
    lines.append(f"- Generated: {report['generated_at']}")
    lines.append(f"- Slides evaluated: {summary['slides_evaluated']}")
    lines.append(f"- Avg before score: {summary['before_avg_score']}")
    lines.append(f"- Avg after score: {summary['after_avg_score']}")
    lines.append(f"- Improved slides: {summary['improved_slides']}/{summary['slides_evaluated']}")
    lines.append("")
    lines.append("## Worst Slides Before (Top 20)")
    lines.append("")
    lines.append("| Pathway | Chapter | Slide | Before | After | Delta |")
    lines.append("|---|---|---|---:|---:|---:|")
    worst = sorted(slides, key=lambda r: r["before"]["metrics"]["score"])[:20]
    for r in worst:
        b = r["before"]["metrics"]["score"]
        a = r["after"]["metrics"]["score"]
        lines.append(f"| {r['pathway_id']} | {r['chapter_id']} | {r['slide_id']} | {b} | {a} | {round(a-b,1)} |")
    lines.append("")
    lines.append("## Largest Improvements (Top 20)")
    lines.append("")
    lines.append("| Pathway | Chapter | Slide | Before | After | Delta |")
    lines.append("|---|---|---|---:|---:|---:|")
    improved = sorted(slides, key=lambda r: r["after"]["metrics"]["score"] - r["before"]["metrics"]["score"], reverse=True)[:20]
    for r in improved:
        b = r["before"]["metrics"]["score"]
        a = r["after"]["metrics"]["score"]
        lines.append(f"| {r['pathway_id']} | {r['chapter_id']} | {r['slide_id']} | {b} | {a} | {round(a-b,1)} |")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Goal: concise but educationally sufficient slides.")
    lines.append("- Target behavior: learner can follow slides without requiring notes for baseline understanding.")
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    root = Path(__file__).resolve().parents[1]
    curriculum = _load_curriculum(root, args.content_file, args.curriculum_file)

    rows = []
    training_rows = []
    for idx, (pathway, chapter, slide) in enumerate(_iter_slides(curriculum), start=1):
        if args.limit and idx > args.limit:
            break
        blocks = slide.get("content_blocks") or []
        notes_text = "\n\n".join(_normalize_ws(b.get("text") or "") for b in blocks if _normalize_ws(b.get("text") or ""))
        if not notes_text:
            continue
        before_h = build_legacy_slide_highlights(blocks, max_items=3, max_chars_per_item=180)
        after_h = build_informative_slide_highlights(blocks, max_items=5, max_chars_per_item=210, max_total_chars=620)

        before_m = _evaluate(blocks, before_h)
        after_m = _evaluate(blocks, after_h)

        row = {
            "pathway_id": pathway.get("id"),
            "pathway_title": pathway.get("title"),
            "chapter_id": chapter.get("id"),
            "chapter_title": chapter.get("title"),
            "slide_id": slide.get("id"),
            "slide_title": slide.get("title"),
            "notes_blocks": blocks,
            "notes_chars": len(notes_text),
            "notes_preview": notes_text[:320] + ("..." if len(notes_text) > 320 else ""),
            "before": {
                "highlights": before_h,
                "metrics": before_m,
                "review": _review_text("before", before_m),
            },
            "after": {
                "highlights": after_h,
                "metrics": after_m,
                "review": _review_text("after", after_m),
            },
            "delta": {
                "score": round(after_m["score"] - before_m["score"], 1),
                "coverage": round(after_m["coverage"] - before_m["coverage"], 3),
                "math_coverage": round(after_m["math_coverage"] - before_m["math_coverage"], 3),
                "density_fit": round(after_m["density_fit"] - before_m["density_fit"], 3),
                "clarity": round(after_m["clarity"] - before_m["clarity"], 3),
            },
        }
        rows.append(row)

        training_rows.append({
            "pathway_id": row["pathway_id"],
            "chapter_id": row["chapter_id"],
            "slide_id": row["slide_id"],
            "slide_title": row["slide_title"],
            "input": {
                "notes_blocks": blocks,
                "current_highlights": before_h,
                "constraints": {
                    "max_items": 5,
                    "max_chars_per_item": 210,
                    "max_total_chars": 620,
                    "goal": "concise but educationally sufficient"
                },
            },
            "target": {
                "optimized_highlights": after_h,
                "rationale": row["after"]["review"],
            },
            "scores": {
                "before": before_m,
                "after": after_m,
            },
        })

    before_avg = round(sum(r["before"]["metrics"]["score"] for r in rows) / max(1, len(rows)), 2)
    after_avg = round(sum(r["after"]["metrics"]["score"] for r in rows) / max(1, len(rows)), 2)
    improved = sum(1 for r in rows if r["after"]["metrics"]["score"] > r["before"]["metrics"]["score"])
    report = {
        "generated_at": _now_iso(),
        "constraints": {
            "max_items": 5,
            "max_chars_per_item": 210,
            "max_total_chars": 620,
            "design_goal": "slides should be concise, readable, and independently instructional; notes are for depth.",
        },
        "summary": {
            "slides_evaluated": len(rows),
            "before_avg_score": before_avg,
            "after_avg_score": after_avg,
            "improved_slides": improved,
        },
        "slides": rows,
    }

    out_json = root / args.out_json
    out_md = root / args.out_md
    out_train = root / args.out_training
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_train.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_markdown(out_md, report)
    with out_train.open("w", encoding="utf-8") as f:
        for row in training_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate before/after slide quality reports.")
    p.add_argument("--content-file", default="content_jsons.txt", help="Path to pathway content JSON file.")
    p.add_argument("--curriculum-file", default="data/curriculum.json", help="Fallback curriculum file.")
    p.add_argument("--out-json", default="reports/slide_quality_before_after.json", help="Output JSON report path.")
    p.add_argument("--out-md", default="reports/slide_quality_before_after.md", help="Output Markdown report path.")
    p.add_argument("--out-training", default="training/slide_quality_pairs.jsonl", help="Training pair export path.")
    p.add_argument("--limit", type=int, default=0, help="Optional max slides to evaluate.")
    return p


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
