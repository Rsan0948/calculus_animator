from __future__ import annotations

import time

import pytest
import sympy as sp

from core.detector import CalculusType
from core.parser import ExpressionParser
from core.solver import CalculusSolver


@pytest.mark.perf
def test_parse_and_solve_smoke_under_reasonable_time_budget():
    parser = ExpressionParser()
    solver = CalculusSolver()
    expressions = [
        "x^5 + 3x^2 - 7x + 1",
        r"\frac{d^5}{dx^5} (x^3 \sin(x^2))",
        r"\lim_{x \to \infty} \left(1+\frac{1}{x}\right)^x",
        r"\int_0^2 x^2 dx",
    ]

    t0 = time.perf_counter()
    for raw in expressions:
        parsed = parser.parse(raw)
        if not parsed.get("success"):
            continue
        expr = parsed["sympy_expr"]
        if raw.startswith(r"\frac{d"):
            out = solver.solve(expr, CalculusType.DERIVATIVE, {"variable": "x", "order": 5})
            assert out["success"] is True
        elif raw.startswith(r"\lim"):
            out = solver.solve(expr, CalculusType.LIMIT, {"variable": "x", "point": "oo"})
            assert out["success"] is True
        elif raw.startswith(r"\int"):
            out = solver.solve(expr, CalculusType.INTEGRAL_DEFINITE, {"variable": "x", "lower": 0, "upper": 2})
            assert out["success"] is True
        else:
            out = solver.solve(expr, CalculusType.SIMPLIFY, {})
            assert out["success"] is True
    elapsed = time.perf_counter() - t0
    # broad smoke threshold to catch pathological regressions without being brittle
    assert elapsed < 6.0


@pytest.mark.perf
def test_solver_bulk_derivative_smoke():
    solver = CalculusSolver()
    x = sp.Symbol("x")
    polys = [sum((i + 1) * x ** i for i in range(1, n)) for n in range(8, 18)]
    t0 = time.perf_counter()
    for p in polys:
        out = solver.solve(p, CalculusType.DERIVATIVE, {"variable": "x"})
        assert out["success"] is True
    elapsed = time.perf_counter() - t0
    assert elapsed < 4.0
