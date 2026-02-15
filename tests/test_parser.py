from __future__ import annotations

import sympy as sp

from core.parser import ExpressionParser


def test_preprocess_normalizes_common_unicode_tokens():
    parser = ExpressionParser()
    out = parser._preprocess("π × x − 1")
    assert "pi" in out
    assert "*" in out
    assert "-" in out


def test_latex_to_sympy_string_inserts_implicit_multiplication():
    parser = ExpressionParser()
    out = parser._latex_to_sympy_str("2x(x+1)")
    assert out == "2*x*(x+1)"


def test_parse_plain_polynomial_returns_symbol_and_variables():
    parser = ExpressionParser()
    result = parser.parse("x^2 + 3x + 2")
    assert result["success"] is True
    assert "x" in result["variables"]
    assert sp.simplify(result["sympy_expr"] - (sp.Symbol("x") ** 2 + 3 * sp.Symbol("x") + 2)) == 0


def test_parse_fraction_latex_falls_back_cleanly():
    parser = ExpressionParser()
    result = parser.parse(r"\frac{1}{x}")
    assert result["success"] is True
    x = sp.Symbol("x")
    assert sp.simplify(result["sympy_expr"] - (1 / x)) == 0


def test_parse_invalid_expression_returns_failure():
    parser = ExpressionParser()
    result = parser.parse(")))")
    assert result["success"] is False
    assert "error" in result

