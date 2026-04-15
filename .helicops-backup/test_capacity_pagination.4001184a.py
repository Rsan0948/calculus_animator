from __future__ import annotations

from api.capacity_slide_worker import _paginate, _wrap_paragraph_lines


class FakeFont:
    def __init__(self, char_px: int = 10):
        self.char_px = char_px

    def size(self, text: str):
        return (len(text) * self.char_px, 20)


def test_wrap_paragraph_lines_hard_breaks_long_words():
    font = FakeFont(char_px=10)
    lines = _wrap_paragraph_lines("fit supercalifragilisticexpialidocious", font, max_width=50)
    assert len(lines) > 1
    assert all(len(line) <= 5 for line in lines[1:])


def test_paginate_spreads_text_across_multiple_pages_with_stable_order():
    font = FakeFont(char_px=8)
    text = "\n\n".join(
        [
            "[CHK-001] synthetic calibration block one with repeated words for wrapping behavior.",
            "[CHK-002] synthetic calibration block two with repeated words for wrapping behavior.",
            "[CHK-003] synthetic calibration block three with repeated words for wrapping behavior.",
            "[CHK-004] synthetic calibration block four with repeated words for wrapping behavior.",
        ]
    )
    pages = _paginate(text, font, max_width=120, max_lines=3)
    assert len(pages) >= 2
    reconstructed = "\n".join(pages)
    assert "[CHK-001]" in reconstructed
    assert "[CHK-004]" in reconstructed


def test_paginate_empty_text_returns_single_empty_page():
    font = FakeFont()
    pages = _paginate("", font, max_width=120, max_lines=3)
    assert pages == [""]
