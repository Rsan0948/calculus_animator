from __future__ import annotations

import pytest

hypothesis = pytest.importorskip("hypothesis")
st = hypothesis.strategies
given = hypothesis.given
settings = hypothesis.settings
HealthCheck = hypothesis.HealthCheck

from math_engine.plugins.calculus.extractor import ExpressionExtractor  # noqa: E402
from math_engine.plugins.calculus.parser import ExpressionParser  # noqa: E402

SAFE_ALPHABET = list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_+-*/^(){}[]\\ ,.=→∞")


@pytest.mark.fuzz
@settings(max_examples=120, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(st.text(alphabet=SAFE_ALPHABET, min_size=0, max_size=120))
def test_parser_never_raises_on_fuzzy_math_like_input(text) -> None:
    parser = ExpressionParser()
    out = parser.parse(text)
    assert isinstance(out, dict)
    assert "success" in out
    if out["success"]:
        assert "sympy_expr" in out
    else:
        assert "error" in out


@pytest.mark.fuzz
@settings(max_examples=120, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(st.text(alphabet=SAFE_ALPHABET, min_size=0, max_size=160))
def test_extractor_never_raises_on_fuzzy_math_like_input(text) -> None:
    extractor = ExpressionExtractor()
    inner, params = extractor.extract(text)
    assert isinstance(inner, str)
    assert isinstance(params, dict)
