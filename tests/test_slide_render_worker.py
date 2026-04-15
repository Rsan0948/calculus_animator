from __future__ import annotations

from api import slide_render_worker as worker


def test_pretty_math_text_formats_exponents_and_fractions() -> None:
    text = r"\frac{d^5}{dx^5} \left(x^3 \sin(x^2)\right)"
    out = worker._pretty_math_text(text)
    assert "d" in out
    assert "sin" in out
    assert "⁵" in out


def test_sup_and_sub_maps_produce_unicode() -> None:
    assert worker._to_sup("12x") == "¹²ˣ"
    assert worker._to_sub("12x") == "₁₂ₓ"
