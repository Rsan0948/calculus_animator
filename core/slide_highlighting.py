"""Heuristics for building concise-but-informative slide highlights from notes."""
from __future__ import annotations

import re
from typing import Dict, List

_KIND_PRIORITY = {"problem": 0, "step": 1, "text": 2, "lesson": 2, "example": 3, "note": 4, "summary": 5, "practice": 6}
_EXPLANATORY_CUES = (
    "because", "means", "so that", "in other words", "therefore", "this means", "important",
    "cannot", "must", "always", "never", "if ", "when ", "where ", "for example", "notice",
)


def _normalize_ws(text: str) -> str:
    return " ".join(str(text or "").split())


def _truncate(text: str, max_chars: int) -> str:
    txt = _normalize_ws(text)
    if len(txt) <= max_chars:
        return txt
    return txt[: max_chars - 3].rstrip() + "..."


def _split_sentences(text: str) -> list[str]:
    txt = _normalize_ws(text)
    if not txt:
        return []
    parts = re.split(r"(?<=[.!?])\s+", txt)
    out = []
    for p in parts:
        q = p.strip()
        if q:
            out.append(q)
    if not out and txt:
        return [txt]
    return out


def _starts_with_prefix(text: str, prefix: str) -> bool:
    return str(text or "").strip().lower().startswith(prefix.strip().lower())


def _label(kind: str, text: str, step_num: int) -> str:
    k = (kind or "text").lower()
    if k == "problem":
        return text if _starts_with_prefix(text, "Problem:") else f"Problem: {text}"
    if k == "example":
        return text if _starts_with_prefix(text, "Example:") else f"Example: {text}"
    if k == "note":
        return text if _starts_with_prefix(text, "Note:") else f"Note: {text}"
    if k == "step":
        if _starts_with_prefix(text, "Step "):
            return text
        return f"Step {step_num}: {text}"
    return text


def _sentence_score(kind: str, sentence: str, position: int) -> float:
    k = (kind or "text").lower()
    base = {
        "problem": 1.25,
        "step": 1.1,
        "text": 1.0,
        "lesson": 1.0,
        "example": 0.95,
        "note": 0.9,
        "summary": 0.9,
        "practice": 0.85,
    }.get(k, 0.8)
    s = sentence.lower()
    cue_bonus = 0.0
    if any(cue in s for cue in _EXPLANATORY_CUES):
        cue_bonus += 0.25
    if re.search(r"[=^/()]|\\frac|\\lim|\\int|\\sin|\\cos|\\tan|sqrt|log|ln", sentence):
        cue_bonus += 0.15
    position_penalty = min(position, 4) * 0.06
    length = len(sentence)
    length_penalty = 0.0
    if length < 50:
        length_penalty += 0.12
    if length > 230:
        length_penalty += 0.12
    return base + cue_bonus - position_penalty - length_penalty


def _score_value(candidate: dict[str, object]) -> float:
    raw_score = candidate.get("score", 0.0)
    if isinstance(raw_score, (int, float)):
        return float(raw_score)
    return 0.0


def build_legacy_slide_highlights(blocks: list[dict], max_items: int = 3, max_chars_per_item: int = 180) -> list[dict]:
    """Return the first sentence of the highest-priority blocks (legacy algorithm).

    Sorts blocks by ``_KIND_PRIORITY``, takes the first sentence of each, and
    applies simple ``"Problem: "`` / ``"Example: "`` / ``"Note: "`` prefixes.
    Used for baseline comparison reports only.

    Args:
        blocks: List of content-block dicts, each with ``"kind"`` and ``"text"``
            keys (as stored in curriculum slide JSON).
        max_items: Maximum number of highlight entries to return.
        max_chars_per_item: Hard character limit applied to each entry.

    Returns:
        A list of ``{"kind": str, "text": str}`` dicts, length ≤ ``max_items``.
        Falls back to ``[{"kind": "text", "text": "No highlight content..."}]``
        when no non-empty blocks are found.
    """
    def first_sentence(text: str) -> str:
        txt = _normalize_ws(text)
        if not txt:
            return ""
        for sep in [". ", "? ", "! "]:
            if sep in txt:
                return txt.split(sep, 1)[0].strip() + (sep.strip() if sep.strip() in ".?!" else "")
        return txt

    highlights = []
    sorted_blocks = sorted(blocks or [], key=lambda b: _KIND_PRIORITY.get((b.get("kind") or "text").lower(), 9))
    for b in sorted_blocks:
        kind = (b.get("kind") or "text").lower()
        sentence = first_sentence(b.get("text") or "")
        if not sentence:
            continue
        sentence = _truncate(sentence, max_chars_per_item)
        if kind == "problem":
            sentence = "Problem: " + sentence
        elif kind == "example":
            sentence = "Example: " + sentence
        elif kind == "note":
            sentence = "Note: " + sentence
        highlights.append({"kind": kind, "text": sentence})
        if len(highlights) >= max_items:
            break
    if not highlights:
        return [{"kind": "text", "text": "No highlight content for this slide."}]
    return highlights


def build_informative_slide_highlights(
    blocks: list[dict],
    max_items: int = 5,
    max_chars_per_item: int = 210,
    max_total_chars: int = 620,
) -> list[dict]:
    """Extract the most educationally valuable sentences from slide content blocks.

    Scores each sentence using ``_sentence_score`` (kind weight + explanatory-cue
    bonus + math-notation bonus − position and length penalties), picks the
    highest-scoring sentences per block, and assembles them in source order to
    preserve narrative flow.  A backfill pass ensures at least 3 items when the
    flow pass is too sparse, and a third pass adds one more entry when total
    character budget is under 260.

    Args:
        blocks: List of content-block dicts with ``"kind"`` and ``"text"`` keys.
        max_items: Maximum number of highlight entries to return.
        max_chars_per_item: Hard truncation limit per entry (appends ``"..."``).
        max_total_chars: Cumulative character budget across all entries; new
            entries are skipped once this is exceeded.

    Returns:
        A list of ``{"kind": str, "text": str}`` dicts, length ≤ ``max_items``.
        Falls back to ``[{"kind": "text", "text": "No highlight content..."}]``
        when no usable content is found.
    """
    if not blocks:
        return [{"kind": "text", "text": "No highlight content for this slide."}]

    non_empty_blocks = [b for b in (blocks or []) if _normalize_ws(b.get("text") or "")]
    single_block_mode = len(non_empty_blocks) == 1

    candidates: List[dict[str, object]] = []
    step_num = 1
    for b_idx, b in enumerate(blocks):
        kind = (b.get("kind") or "text").lower()
        text = b.get("text") or ""
        sentences = _split_sentences(text)
        if not sentences:
            continue

        # Keep 1-2 sentences depending on block kind and density.
        keep = 1
        if single_block_mode:
            keep = min(3, len(sentences))
        elif kind in ("text", "lesson", "summary") and len(sentences) > 1:
            keep = 2
        if kind == "step":
            keep = 1
        if kind in ("problem", "example", "note"):
            keep = 1
            if len(sentences) > 1 and len(_normalize_ws(text)) > 140:
                keep = 2

        scored = []
        for s_idx, sentence in enumerate(sentences):
            score = _sentence_score(kind, sentence, s_idx)
            scored.append((score, s_idx, sentence))
        scored.sort(key=lambda t: (-t[0], t[1]))

        picked = sorted(scored[:keep], key=lambda t: t[1])
        for _, s_idx, sentence in picked:
            labeled = _label(kind, sentence, step_num)
            candidates.append({
                "kind": kind,
                "text": _truncate(labeled, max_chars_per_item),
                "score": _sentence_score(kind, sentence, s_idx),
                "block_index": b_idx,
                "sentence_index": s_idx,
            })
        if kind == "step":
            step_num += 1

    if not candidates:
        return [{"kind": "text", "text": "No highlight content for this slide."}]

    # Ensure flow: keep ordering by source location, but skip weak duplicates.
    out: List[Dict[str, str]] = []
    seen = set()
    total_chars = 0
    for c in sorted(candidates, key=lambda x: (x["block_index"], x["sentence_index"])):
        text_value = str(c.get("text", ""))
        key = re.sub(r"[^a-z0-9]+", "", text_value.lower())
        if not key or key in seen:
            continue
        if len(key) < 18:
            continue
        if len(out) >= max_items:
            break
        next_total = total_chars + len(text_value)
        if out and next_total > max_total_chars:
            break
        out.append({"kind": str(c.get("kind", "text")), "text": text_value})
        seen.add(key)
        total_chars = next_total

    # Backfill with strongest candidates if flow pass was too sparse.
    if len(out) < min(3, max_items):
        for c in sorted(
            candidates,
            key=lambda x: (-_score_value(x), x["block_index"], x["sentence_index"]),
        ):
            text_value = str(c.get("text", ""))
            key = re.sub(r"[^a-z0-9]+", "", text_value.lower())
            if not key or key in seen:
                continue
            if len(out) >= max_items:
                break
            next_total = total_chars + len(text_value)
            if out and next_total > max_total_chars:
                continue
            out.append({"kind": str(c.get("kind", "text")), "text": text_value})
            seen.add(key)
            total_chars = next_total

    # If still too thin, add one more explanatory sentence when available.
    if len(out) < max_items and total_chars < 260:
        for c in sorted(
            candidates,
            key=lambda x: (-_score_value(x), x["block_index"], x["sentence_index"]),
        ):
            text_value = str(c.get("text", ""))
            key = re.sub(r"[^a-z0-9]+", "", text_value.lower())
            if not key or key in seen:
                continue
            next_total = total_chars + len(text_value)
            if out and next_total > max_total_chars:
                continue
            out.append({"kind": str(c.get("kind", "text")), "text": text_value})
            seen.add(key)
            total_chars = next_total
            if len(out) >= max_items or total_chars >= 300:
                break

    if not out:
        return [{"kind": "text", "text": "No highlight content for this slide."}]
    return out
