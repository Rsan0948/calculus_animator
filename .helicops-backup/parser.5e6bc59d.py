"""Robust LaTeX → SymPy parser with multiple fallback strategies."""
import re

from sympy import (
    Abs,
    E,
    acos,
    asin,
    atan,
    cos,
    cot,
    csc,
    exp,
    ln,
    log,
    oo,
    pi,
    sec,
    sin,
    sqrt,
    symbols,
    sympify,
    tan,
)
from sympy.parsing.latex import parse_latex

_COMMON = {
    r"\sin": "sin", r"\cos": "cos", r"\tan": "tan",
    r"\sec": "sec", r"\csc": "csc", r"\cot": "cot",
    r"\arcsin": "asin", r"\arccos": "acos", r"\arctan": "atan",
    r"\ln": "log", r"\log": "log", r"\exp": "exp",
    r"\sqrt": "sqrt", r"\pi": "pi", r"\infty": "oo",
    r"\left": "", r"\right": "", r"\,": " ", r"\!": "",
    r"\cdot": "*", r"\times": "*",
}


class ExpressionParser:
    def __init__(self):
        self._x, self._y, self._z, self._t = symbols("x y z t")
        self._n, self._k = symbols("n k", integer=True)

    def parse(self, latex_str: str) -> dict:
        """Parse a LaTeX math expression into a SymPy object.

        Tries three strategies in order: SymPy's ``parse_latex``, a manual
        translation pass, and finally a raw ``sympify`` call.  The first
        strategy that succeeds is returned.

        Args:
            latex_str: A LaTeX string such as ``r"\\frac{d}{dx} x^2"`` or
                ``"x^2 + 3x - 1"``.

        Returns:
            On success: ``{"success": True, "sympy_expr": Expr, "latex": str,
            "variables": list[str], "raw": str}``.
            On failure: ``{"success": False, "error": str, "latex": str}``.
        """
        cleaned = self._preprocess(latex_str)
        expr = None
        error = None

        # Strategy 1: SymPy parse_latex
        try:
            expr = parse_latex(cleaned)
        except Exception:
            pass

        # Strategy 2: manual translation to SymPy string
        if expr is None:
            try:
                py_str = self._latex_to_sympy_str(cleaned)
                expr = sympify(py_str, locals={
                    "x": self._x, "y": self._y, "z": self._z, "t": self._t,
                    "n": self._n, "k": self._k, "pi": pi, "e": E, "E": E,
                    "sin": sin, "cos": cos, "tan": tan, "sec": sec,
                    "csc": csc, "cot": cot, "asin": asin, "acos": acos,
                    "atan": atan, "log": log, "ln": ln, "exp": exp,
                    "sqrt": sqrt, "Abs": Abs, "oo": oo,
                })
            except Exception:
                pass

        # Strategy 3: try raw sympify
        if expr is None:
            try:
                expr = sympify(cleaned.replace("^", "**"))
            except Exception as e:
                error = str(e)

        if expr is not None:
            return {
                "success": True,
                "sympy_expr": expr,
                "latex": latex_str,
                "variables": sorted(str(s) for s in expr.free_symbols),
                "raw": str(expr),
            }
        return {"success": False, "error": error or "Unable to parse expression", "latex": latex_str}

    # ── helpers ──────────────────────────────────────────────────────
    def _preprocess(self, latex: str) -> str:
        s = latex.strip()
        s = re.sub(r"\\left|\\right", "", s)
        s = s.replace(r"\,", " ").replace(r"\!", "")
        s = s.replace("π", "pi").replace("∞", "oo")
        s = s.replace("×", "*").replace("·", "*")
        s = s.replace("−", "-")
        s = re.sub(r"\\\s+", " ", s)
        return re.sub(r"\\operatorname\{(\w+)\}", r"\\\1", s)

    def _latex_to_sympy_str(self, latex: str) -> str:
        s = latex
        # handle \frac{a}{b} → ((a)/(b))
        while r"\frac" in s:
            s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"((\1)/(\2))", s)
            s = re.sub(
                r"\\frac\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}",
                r"((\1)/(\2))", s,
            )
            if r"\frac" in s:
                break
        # handle \sqrt[n]{x} and \sqrt{x}
        s = re.sub(r"\\sqrt\[([^\]]+)\]\{([^{}]+)\}", r"((\2)**(1/(\1)))", s)
        s = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", s)
        for pat, rep in _COMMON.items():
            s = s.replace(pat, rep)
        s = s.replace("^", "**").replace("{", "(").replace("}", ")")
        # insert multiplication: 2x → 2*x, )x → )*x, x( → x*(
        s = re.sub(r"(\d)([a-zA-Z(])", r"\1*\2", s)
        s = re.sub(r"\)(\w)", r")*\1", s)
        s = re.sub(r"\)\(", r")*(", s)
        s = re.sub(r"(?<![a-zA-Z])([a-zA-Z])\(", r"\1*(", s)
        s = re.sub(r"([a-zA-Z0-9\)])\s+([a-zA-Z])", r"\1*\2", s)
        return re.sub(r"\s+", " ", s).strip()
