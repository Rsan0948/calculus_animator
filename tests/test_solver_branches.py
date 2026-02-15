from __future__ import annotations

import sympy as sp

import core.solver as solver_module
from core.detector import CalculusType
from core.solver import CalculusSolver


def test_solve_dispatch_exception_is_captured(monkeypatch):
    solver = CalculusSolver()
    monkeypatch.setattr(solver, "_simplify", lambda expr, p: (_ for _ in ()).throw(RuntimeError("boom")))
    out = solver.solve(sp.Symbol("x"), CalculusType.UNKNOWN, {})
    assert out["success"] is False
    assert "boom" in out["error"]


def test_identify_diff_rule_additional_branches():
    solver = CalculusSolver()
    x = sp.Symbol("x")
    y = sp.Symbol("y")
    assert solver._identify_diff_rule(sp.Integer(4), x) == "constant"
    assert solver._identify_diff_rule(x, x) == "basic"
    assert solver._identify_diff_rule(y * x, x) == "constant_multiple"
    assert solver._identify_diff_rule(x**x, x) == "logarithmic_diff"
    assert solver._identify_diff_rule(2**x, x) == "exponential_rule"
    assert solver._identify_diff_rule(sp.log(x), x) == "logarithm_rule"
    assert solver._identify_diff_rule(sp.sqrt(x), x) == "power_rule"


def test_diff_substeps_chain_and_quotient_branches():
    solver = CalculusSolver()
    x = sp.Symbol("x")
    chain_expr = sp.sin(x**2)
    chain_result = sp.diff(chain_expr, x)
    chain_steps = solver._diff_substeps(chain_expr, chain_result, x, "chain_rule")
    assert chain_steps and chain_steps[0]["rule"] == "chain_rule_detail"

    quot_expr = (x**2 + 1) / sp.cos(x)
    quot_result = sp.diff(quot_expr, x)
    quot_steps = solver._diff_substeps(quot_expr, quot_result, x, "quotient_rule")
    assert quot_steps and quot_steps[0]["rule"] == "quotient_rule_detail"


def test_limit_direct_substitution_branch():
    solver = CalculusSolver()
    x = sp.Symbol("x")
    out = solver.solve(x**2 + 1, CalculusType.LIMIT, {"variable": "x", "point": 2})
    assert out["success"] is True
    assert sp.simplify(out["result"] - 5) == 0
    assert out["steps"][0]["rule"] == "direct_substitution"


def test_taylor_alias_branch():
    solver = CalculusSolver()
    x = sp.Symbol("x")
    out = solver.solve(sp.sin(x), CalculusType.TAYLOR_SERIES, {"variable": "x", "point": 0, "order": 5})
    assert out["success"] is True
    assert out["steps"][0]["rule"] == "series_expansion"


def test_ode_success_branch():
    solver = CalculusSolver()
    x = sp.Symbol("x")
    y = sp.Function("y")
    ode_expr = sp.Eq(sp.diff(y(x), x) - y(x), 0)
    out = solver.solve(ode_expr, CalculusType.DIFFERENTIAL_EQ, {"variable": "x"})
    assert out["success"] is True
    assert out["steps"][0]["rule"] == "ode_solution"


def test_ode_failure_branch():
    solver = CalculusSolver()
    out = solver.solve(sp.Symbol("x"), CalculusType.DIFFERENTIAL_EQ, {"variable": "x"})
    assert out["success"] is False
    assert out["error"].startswith("ODE solver:")


def test_extract_integral_manual_steps_when_disabled(monkeypatch):
    solver = CalculusSolver()
    x = sp.Symbol("x")
    monkeypatch.setattr(solver_module, "HAS_MANUAL", False)
    out = solver._extract_integral_manual_steps(x, x)
    assert out == []


def test_extract_integral_manual_steps_exception(monkeypatch):
    solver = CalculusSolver()
    x = sp.Symbol("x")
    monkeypatch.setattr(solver_module, "HAS_MANUAL", True)
    monkeypatch.setattr(solver_module, "_integral_steps", lambda expr, var: (_ for _ in ()).throw(RuntimeError("err")))
    out = solver._extract_integral_manual_steps(x, x)
    assert out == []


def test_walk_int_steps_depth_and_children():
    solver = CalculusSolver()
    out = []

    class Node:
        def __init__(self, context=None, substep=None, substeps=None):
            self.context = context
            self.substep = substep
            self.substeps = substeps

    deep = Node(context=sp.Symbol("z"))
    solver._walk_int_steps(deep, out, 16)
    assert out == []

    child1 = Node(context=sp.Symbol("x"))
    child2 = Node(context=sp.Symbol("y"))
    parent = Node(context=sp.Symbol("w"), substeps=[child1, child2])
    solver._walk_int_steps(parent, out, 0)
    assert len(out) >= 3
    assert all("rule" in step for step in out)


def test_to_sympy_num_symbol_fallback():
    solver = CalculusSolver()
    val = solver._to_sympy_num("abc_not_number")
    assert isinstance(val, sp.Symbol)
    assert str(val) == "abc_not_number"
