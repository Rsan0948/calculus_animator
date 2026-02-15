from __future__ import annotations

import sympy as sp

from core.detector import CalculusType
from core.solver import CalculusSolver


def test_derivative_basic_power_rule():
    solver = CalculusSolver()
    x = sp.Symbol("x")
    out = solver.solve(x**3, CalculusType.DERIVATIVE, {"variable": "x"})
    assert out["success"] is True
    assert sp.simplify(out["result"] - 3 * x**2) == 0
    assert out["steps"]
    assert out["steps"][0]["rule"] in {"power_rule", "basic", "chain_rule"}


def test_derivative_higher_order():
    solver = CalculusSolver()
    x = sp.Symbol("x")
    out = solver.solve(x**3, CalculusType.DERIVATIVE, {"variable": "x", "order": 2})
    assert out["success"] is True
    assert sp.simplify(out["result"] - 6 * x) == 0
    assert len(out["steps"]) >= 2


def test_indefinite_integral_appends_constant():
    solver = CalculusSolver()
    x = sp.Symbol("x")
    out = solver.solve(x, CalculusType.INTEGRAL_INDEFINITE, {"variable": "x"})
    assert out["success"] is True
    assert sp.simplify(out["result"] - x**2 / 2) == 0
    assert out["result_latex"].endswith(" + C")
    assert out["steps"][-1]["rule"] == "integration_result"


def test_definite_integral_uses_fundamental_theorem_step():
    solver = CalculusSolver()
    x = sp.Symbol("x")
    out = solver.solve(x, CalculusType.INTEGRAL_DEFINITE, {"variable": "x", "lower": 0, "upper": 1})
    assert out["success"] is True
    assert sp.simplify(out["result"] - sp.Rational(1, 2)) == 0
    assert any(step["rule"] == "fundamental_theorem" for step in out["steps"])


def test_limit_indeterminate_path_has_explanatory_steps():
    solver = CalculusSolver()
    x = sp.Symbol("x")
    expr = sp.sin(x) / x
    out = solver.solve(expr, CalculusType.LIMIT, {"variable": "x", "point": 0})
    assert out["success"] is True
    assert sp.simplify(out["result"] - 1) == 0
    rules = [s["rule"] for s in out["steps"]]
    assert "indeterminate" in rules
    assert "lhopital_or_algebraic" in rules


def test_simplify_path_returns_shorter_expression():
    solver = CalculusSolver()
    x = sp.Symbol("x")
    out = solver.solve((x**2 - 1) / (x - 1), CalculusType.SIMPLIFY, {})
    assert out["success"] is True
    assert sp.simplify(out["result"] - (x + 1)) == 0
    assert out["steps"][0]["rule"] == "simplification"


def test_to_sympy_num_handles_infinity_tokens():
    solver = CalculusSolver()
    assert solver._to_sympy_num(r"\infty") == sp.oo
    assert solver._to_sympy_num(r"-\infty") == -sp.oo
    assert solver._to_sympy_num("2.5") == sp.S("2.5")

