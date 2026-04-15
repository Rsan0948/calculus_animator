from __future__ import annotations

from math_engine.plugins.calculus.slide_highlighting import build_informative_slide_highlights


def test_no_duplicate_note_or_example_prefixes() -> None:
    blocks = [
        {"kind": "note", "text": "Note: The vertical line test checks if any x has multiple outputs."},
        {"kind": "example", "text": "Example: If f(x)=x^2, then f(3)=9."},
    ]
    highlights = build_informative_slide_highlights(blocks, max_items=5)
    texts = [h["text"] for h in highlights]
    assert all("Note: Note:" not in t for t in texts)
    assert all("Example: Example:" not in t for t in texts)


def test_single_dense_block_keeps_multiple_sentences_for_learning_value() -> None:
    blocks = [
        {
            "kind": "text",
            "text": (
                "A function maps each input to exactly one output. "
                "The vertical line test helps verify this on a graph because one x-value should not hit two y-values. "
                "Different inputs can still share the same output. "
                "This matters when deciding whether an equation represents a valid function."
            ),
        }
    ]
    highlights = build_informative_slide_highlights(blocks, max_items=5, max_total_chars=620)
    assert len(highlights) >= 2
    assert any("vertical line test" in h["text"].lower() for h in highlights)


def test_highlights_respect_item_limit() -> None:
    blocks = [{"kind": "step", "text": f"Step {i} explanation with enough detail to be selected."} for i in range(1, 10)]
    highlights = build_informative_slide_highlights(blocks, max_items=4)
    assert len(highlights) <= 4
