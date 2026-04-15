from __future__ import annotations

from core.slide_highlighting import (
    _label,
    _normalize_ws,
    _sentence_score,
    _split_sentences,
    _starts_with_prefix,
    _truncate,
    build_informative_slide_highlights,
    build_legacy_slide_highlights,
)


def test_normalize_and_truncate_helpers():
    assert _normalize_ws("  a   b \n c  ") == "a b c"
    assert _truncate("abc", 10) == "abc"
    assert _truncate("abcdefghij", 6) == "abc..."


def test_split_sentences_and_prefix_helpers():
    assert _split_sentences("") == []
    assert _split_sentences("One. Two? Three!") == ["One.", "Two?", "Three!"]
    assert _starts_with_prefix("Note: hello", "note:")
    assert not _starts_with_prefix("Example: hello", "note:")


def test_label_helper_prefixes_once():
    assert _label("problem", "Find x", 1).startswith("Problem:")
    assert _label("example", "Example: already", 1) == "Example: already"
    assert _label("note", "Note: already", 1) == "Note: already"
    assert _label("step", "Do this", 3).startswith("Step 3:")
    assert _label("text", "Plain", 1) == "Plain"


def test_sentence_score_cues_and_lengths():
    base = _sentence_score("text", "This is short.", 0)
    with_cue = _sentence_score("text", "This means we should use substitution.", 0)
    longish = _sentence_score("text", "x = y / z and therefore use this because it is important.", 0)
    assert with_cue > base
    assert longish > base


def test_legacy_highlights_empty_and_prefixing():
    assert build_legacy_slide_highlights([]) == [{"kind": "text", "text": "No highlight content for this slide."}]
    blocks = [
        {"kind": "example", "text": "Use f(x)=x^2. Then evaluate."},
        {"kind": "note", "text": "Pay attention to signs."},
    ]
    out = build_legacy_slide_highlights(blocks, max_items=2)
    assert out[0]["text"].startswith("Example:")
    assert out[1]["text"].startswith("Note:")


def test_informative_highlights_handles_sparse_and_backfill_paths():
    blocks = [
        {"kind": "text", "text": "a. b. c."},  # very short keys likely filtered by len(key) < 18
        {"kind": "text", "text": "This means we choose a method because structure is important."},
        {"kind": "note", "text": "Notice this also works when x approaches zero and we use limits."},
    ]
    out = build_informative_slide_highlights(blocks, max_items=5, max_chars_per_item=140, max_total_chars=260)
    assert out
    assert len(out) <= 5
    assert all(item["text"] for item in out)


def test_informative_highlights_no_candidates_fallback():
    blocks = [{"kind": "text", "text": "   "}]
    out = build_informative_slide_highlights(blocks)
    assert out == [{"kind": "text", "text": "No highlight content for this slide."}]

