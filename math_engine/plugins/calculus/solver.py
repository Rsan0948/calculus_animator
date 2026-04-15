"""SymPy-based solver with detailed step extraction."""
from typing import Any, Dict, Optional

from sympy import (
    Eq,
    Function,
    S,
    Symbol,
    cancel,
    cos,
    cot,
    csc,
    diff,
    dsolve,
    exp,
    expand,
    factor,
    integrate,
    latex,
    limit,
    log,
    nan,
    oo,
    sec,
    series,
    simplify,
    sin,
    sqrt,
    tan,
    trigsimp,
    zoo,
)

from .detector import CalculusType

try:
    from sympy.integrals.manualintegrate import integral_steps as _integral_steps
    HAS_MANUAL = True
except ImportError:
    HAS_MANUAL = False


def _sym(name, **kw):
    return Symbol(name, **kw)


class CalculusSolver:
    def solve(self, expr, calc_type: CalculusType, params: Optional[Dict[str, Any]] = None) -> dict:
        """Solve a calculus expression and return step-by-step results.

        Dispatches to a specialised solver based on ``calc_type``, collects
        intermediate steps with rule names, and returns a uniform result dict.

        Args:
            expr: A SymPy expression to operate on.
            calc_type: A ``CalculusType`` enum value that selects the solver
                (derivative, integral, limit, series, ODE, or simplify).
            params: Optional dict of operation parameters, e.g.
                ``{"variable": "x", "order": 2}`` for a derivative or
                ``{"lower": 0, "upper": 1}`` for a definite integral.

        Returns:
            On success: ``{"success": True, "result": str, "result_latex": str,
            "steps": list[dict]}``.  Each step dict has keys ``"description"``,
            ``"before"``, ``"after"``, and ``"rule"``.
            On failure: ``{"success": False, "error": str, "steps": []}``.
        """
        params = params or {}
        dispatch = {
            CalculusType.DERIVATIVE: self._derivative,
            CalculusType.INTEGRAL_INDEFINITE: self._integral_indef,
            CalculusType.INTEGRAL_DEFINITE: self._integral_def,
            CalculusType.LIMIT: self._limit,
            CalculusType.SERIES: self._series,
            CalculusType.TAYLOR_SERIES: self._taylor,
            CalculusType.DIFFERENTIAL_EQ: self._ode,
            CalculusType.SIMPLIFY: self._simplify,
        }
        fn = dispatch.get(calc_type, self._simplify)
        try:
            return fn(expr, params)
        except Exception as e:
            return {"success": False, "error": str(e), "steps": []}

    # ── derivative ───────────────────────────────────────────────
    def _derivative(self, expr, p):
        var = _sym(p.get("variable", "x"))
        order = int(p.get("order", 1))
        steps = []
        current = expr
        for i in range(order):
            result = diff(current, var)
            rule = self._identify_diff_rule(current, var)
            steps.append({
                "description": f"Differentiate with respect to {var}"\
                               + (f" (order {i+1})" if order > 1 else ""),
                "before": latex(current),
                "after": latex(result),
                "rule": rule,
            })
            # expand intermediate sub-steps for common rules
            sub = self._diff_substeps(current, result, var, rule)
            if sub:
                steps.extend(sub)
            current = result
        simplified = simplify(current)
        if simplified != current:
            steps.append({
                "description": "Simplify",
                "before": latex(current),
                "after": latex(simplified),
                "rule": "simplification",
            })
            current = simplified
        return self._ok(current, steps)

    def _diff_substeps(self, expr, result, var, rule):
        """Generate extra explanatory sub-steps for known rules."""
        subs = []
        if rule == "product_rule" and expr.is_Mul:
            funcs = [a for a in expr.args if a.has(var)]
            if len(funcs) == 2:
                f, g = funcs[0], funcs[1]
                coeff = expr / (f * g)
                subs.append({
                    "description": f"Product rule: (fg)' = f'g + fg'  where f={latex(f)}, g={latex(g)}",
                    "before": latex(expr),
                    "after": latex(coeff * (diff(f, var)*g + f*diff(g, var))),
                    "rule": "product_rule_detail",
                })
        elif rule == "chain_rule":
            subs.append({
                "description": "Chain rule: d/dx f(g(x)) = f'(g(x))·g'(x)",
                "before": latex(expr),
                "after": latex(result),
                "rule": "chain_rule_detail",
            })
        elif rule == "quotient_rule":
            n, d = expr.as_numer_denom()
            subs.append({
                "description": "Quotient rule: (f/g)' = (f'g − fg') / g²",
                "before": f"f = {latex(n)},\\; g = {latex(d)}",
                "after": latex(result),
                "rule": "quotient_rule_detail",
            })
        return subs

    def _identify_diff_rule(self, expr, var) -> str:
        """Identify the primary differentiation rule that applies to ``expr``.

        Args:
            expr: The SymPy expression to classify.
            var: The differentiation variable (a SymPy ``Symbol``).

        Returns:
            A rule name string such as ``"power_rule"``, ``"product_rule"``,
            ``"chain_rule"``, ``"quotient_rule"``, ``"trig_rule"``,
            ``"exponential_rule"``, ``"logarithm_rule"``, ``"sum_rule"``,
            ``"constant_multiple"``, ``"constant"``, or ``"basic"``.
        """
        if not expr.has(var):
            return "constant"
        if expr == var:
            return "basic"
        if expr.is_Add:
            return "sum_rule"
        if expr.is_Mul:
            dep = [a for a in expr.args if a.has(var)]
            return "product_rule" if len(dep) > 1 else "constant_multiple"
        if expr.is_Pow:
            base, ex = expr.as_base_exp()
            if base.has(var) and ex.has(var):
                return "logarithmic_diff"
            if base.has(var) and not ex.has(var):
                return "chain_rule" if base != var else "power_rule"
            if ex.has(var):
                return "exponential_rule"
        if expr.func in (sin, cos, tan, sec, csc, cot):
            return "trig_rule"
        if expr.func == exp:
            return "exponential_rule"
        if expr.func == log:
            return "logarithm_rule"
        if expr.func == sqrt:
            return "power_rule"
        # composite
        if len(expr.args) > 0 and any(a.has(var) and a != var for a in expr.args):
            return "chain_rule"
        return "basic"

    # ── indefinite integral ──────────────────────────────────────
    def _integral_indef(self, expr, p) -> dict:
        var = _sym(p.get("variable", "x"))
        steps = self._extract_integral_manual_steps(expr, var)
        result = integrate(expr, var)
        if result.has(integrate):
            return {"success": False, "error": "SymPy could not find a closed-form antiderivative.", "steps": []}
        steps.append({
            "description": "Antiderivative",
            "before": latex(expr),
            "after": latex(result) + " + C",
            "rule": "integration_result",
        })
        return self._ok(result, steps, suffix=" + C")

    # ── definite integral ────────────────────────────────────────
    def _integral_def(self, expr, p):
        var = _sym(p.get("variable", "x"))
        lo = self._to_sympy_num(p.get("lower", 0))
        hi = self._to_sympy_num(p.get("upper", 1))
        antideriv = integrate(expr, var)
        steps = [{
            "description": "Find the antiderivative F(x)",
            "before": f"\\int {latex(expr)}\\,d{var}",
            "after": latex(antideriv),
            "rule": "antiderivative",
        }]
        upper_val = antideriv.subs(var, hi)
        lower_val = antideriv.subs(var, lo)
        steps.append({
            "description": f"Evaluate F({latex(hi)}) − F({latex(lo)})",
            "before": f"F({latex(hi)}) - F({latex(lo)}) = {latex(upper_val)} - {latex(lower_val)}",
            "after": latex(simplify(upper_val - lower_val)),
            "rule": "fundamental_theorem",
        })
        result = integrate(expr, (var, lo, hi))
        return self._ok(result, steps)

    # ── limit ────────────────────────────────────────────────────
    def _limit(self, expr, p):
        var = _sym(p.get("variable", "x"))
        pt = self._to_sympy_num(p.get("point", 0))
        direction = p.get("direction", "+-")
        steps = []
        # direct substitution attempt
        try:
            direct = expr.subs(var, pt)
            if direct.is_finite and direct not in (zoo, nan, S.NaN):
                steps.append({
                    "description": f"Direct substitution: plug {var} = {latex(pt)}",
                    "before": latex(expr),
                    "after": latex(direct),
                    "rule": "direct_substitution",
                })
                return self._ok(direct, steps)
        except Exception:
            pass
        steps.append({
            "description": "Direct substitution yields indeterminate form",
            "before": latex(expr),
            "after": "\\text{indeterminate}",
            "rule": "indeterminate",
        })
        result = limit(expr, var, pt, direction)
        steps.append({
            "description": "Apply limit techniques (L'Hôpital / algebraic)",
            "before": f"\\lim_{{{latex(var)} \\to {latex(pt)}}} {latex(expr)}",
            "after": latex(result),
            "rule": "lhopital_or_algebraic",
        })
        return self._ok(result, steps)

    # ── series / Taylor ──────────────────────────────────────────
    def _series(self, expr, p):
        var = _sym(p.get("variable", "x"))
        pt = self._to_sympy_num(p.get("point", 0))
        order = int(p.get("order", 6))
        result = series(expr, var, pt, order)
        steps = [{
            "description": f"Expand in series around {var} = {latex(pt)} to order {order}",
            "before": latex(expr),
            "after": latex(result),
            "rule": "series_expansion",
        }]
        return self._ok(result, steps)

    def _taylor(self, expr, p):
        return self._series(expr, p)

    # ── ODE ──────────────────────────────────────────────────────
    def _ode(self, expr, p) -> dict:
        var = _sym(p.get("variable", "x"))
        f = Function("y")
        try:
            eq = Eq(expr, 0) if not isinstance(expr, Eq) else expr
            result = dsolve(eq, f(var))
            steps = [{
                "description": "Solve ordinary differential equation",
                "before": latex(eq),
                "after": latex(result),
                "rule": "ode_solution",
            }]
            return self._ok(result, steps)
        except Exception as e:
            return {"success": False, "error": f"ODE solver: {e}", "steps": []}

    # ── simplify fallback ────────────────────────────────────────
    def _simplify(self, expr, p):
        results = [(expr, "original")]
        for fn, name in [(expand, "expand"), (factor, "factor"),
                          (trigsimp, "trigsimp"), (cancel, "cancel"),
                          (simplify, "simplify")]:
            try:
                r = fn(expr)
                if r != expr:
                    results.append((r, name))
            except Exception:
                pass
        best = min(results, key=lambda r: len(str(r[0])))
        steps = [{
            "description": f"Simplify ({best[1]})",
            "before": latex(expr),
            "after": latex(best[0]),
            "rule": "simplification",
        }]
        return self._ok(best[0], steps)

    # ── helpers ──────────────────────────────────────────────────
    def _ok(self, result, steps, suffix: str="") -> dict:
        return {
            "success": True,
            "result": str(result),
            "result_latex": latex(result) + suffix,
            "steps": steps,
        }

    @staticmethod
    def _to_sympy_num(v):
        """Convert a limit/bound value to a SymPy numeric object.

        Recognises infinity shorthands (``"oo"``, ``"\\infty"``, ``"-oo"``)
        and falls back to a ``Symbol`` if the value cannot be parsed as a
        number.

        Args:
            v: The value to convert — may be an ``int``, ``float``, or a
               string such as ``"0"``, ``"oo"``, ``"-\\infty"``, or ``"pi"``.

        Returns:
            A SymPy ``S`` (integer/rational), ``oo``, ``-oo``, or ``Symbol``.
        """
        if isinstance(v, (int, float)):
            return S(v)
        s = str(v).strip().replace(" ", "")
        if s in ("oo", "\\infty", "+\\infty", "inf"):
            return oo
        if s in ("-oo", "-\\infty", "-inf"):
            return -oo
        try:
            return S(s)
        except Exception:
            return Symbol(s)

    def _extract_integral_manual_steps(self, expr, var) -> list:
        if not HAS_MANUAL:
            return []
        try:
            obj = _integral_steps(expr, var)
            out = []
            self._walk_int_steps(obj, out, 0)
            return out
        except Exception:
            return []

    def _walk_int_steps(self, obj, out, depth) -> None:
        if depth > 15:
            return
        if not isinstance(obj, (str, int, float, bool, type(None))):
            name = obj.__class__.__name__
            context = getattr(obj, "context", None)
            if context is not None:
                out.append({
                    "description": name.replace("Rule", " Rule").strip(),
                    "before": latex(context) if hasattr(context, "free_symbols") else str(context),
                    "after": "",
                    "rule": name.lower(),
                })
            for attr in ("substep", "substeps"):
                child = getattr(obj, attr, None)
                if child is None:
                    continue
                if isinstance(child, (list, tuple)):
                    for c in child:
                        self._walk_int_steps(c, out, depth + 1)
                else:
                    self._walk_int_steps(child, out, depth + 1)
