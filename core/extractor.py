r"""Extract the inner expression and parameters from full LaTeX notation."""
import re
from typing import Any, Dict, Optional


class ExpressionExtractor:
    r"""Pull inner expressions out of \frac{d}{dx}, \int, \lim, and similar forms."""

    def extract(
        self,
        latex: str,
        explicit_type: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ):
        """Return (inner_latex, merged_params) with operation notation stripped."""
        _ = explicit_type  # reserved for future explicit-type extraction overrides
        params = dict(params or {})

        # derivative
        m = re.search(
            r"\\frac\{d(?:\^(\d+))?\}\{d([a-z])(?:\^(\d+))?\}\s*(.*)",
            latex, re.DOTALL,
        )
        if m:
            order = int(m.group(1) or m.group(3) or 1)
            params.setdefault("variable", m.group(2))
            params["order"] = order
            return m.group(4).strip() or latex, params

        # plain derivative d^n/dx^n ...
        m = re.search(
            r"\bd(?:\^(\d+))?\s*/\s*d([a-z])(?:\^(\d+))?\s*(.*)",
            latex, re.DOTALL,
        )
        if m:
            order = int(m.group(1) or m.group(3) or 1)
            params.setdefault("variable", m.group(2))
            params["order"] = order
            return m.group(4).strip() or latex, params

        # partial derivative
        m = re.search(
            r"\\frac\{\\partial(?:\^(\d+))?\}\{\\partial\s*([a-z])(?:\^(\d+))?\}\s*(.*)",
            latex, re.DOTALL,
        )
        if m:
            order = int(m.group(1) or m.group(3) or 1)
            params.setdefault("variable", m.group(2))
            params["order"] = order
            return m.group(4).strip() or latex, params

        # prime notation  f'(x), y''
        m = re.match(r"([a-zA-Z]+)('+)\s*(?:\(([a-z])\))?", latex)
        if m:
            params["order"] = len(m.group(2))
            params.setdefault("variable", m.group(3) or "x")
            # can't extract expression from f' alone
            return latex, params

        # definite integral  \int_{a}^{b} ... dx
        m = re.search(
            r"\\int_\{([^{}]+)\}\^\{([^{}]+)\}\s*(.*?)\s*d([a-z])",
            latex, re.DOTALL,
        )
        if not m:
            m = re.search(
                r"\\int_([^\s^_{}]+)\^([^\s{}]+)\s*(.*?)\s*d([a-z])",
                latex, re.DOTALL,
            )
        if m:
            params["lower"] = self._parse_bound(m.group(1))
            params["upper"] = self._parse_bound(m.group(2))
            params.setdefault("variable", m.group(4))
            return m.group(3).strip(), params

        # plain definite integral int_a^b ... dx / ∫_a^b ... dx
        m = re.search(
            r"(?:∫|int)_\{?([^\s^{}]+)\}?\^\{?([^\s{}]+)\}?\s*(.*?)\s*d\s*([a-z])",
            latex, re.DOTALL,
        )
        if m:
            params["lower"] = self._parse_bound(m.group(1))
            params["upper"] = self._parse_bound(m.group(2))
            params.setdefault("variable", m.group(4))
            return m.group(3).strip(), params

        # indefinite integral  \int ... dx
        m = re.search(r"\\int\s*(.*?)\s*d([a-z])", latex, re.DOTALL)
        if m:
            params.setdefault("variable", m.group(2))
            return m.group(1).strip(), params

        # plain indefinite integral int ... dx / ∫ ... dx
        m = re.search(r"(?:∫|int)\s*(.*?)\s*d\s*([a-z])", latex, re.DOTALL)
        if m:
            params.setdefault("variable", m.group(2))
            return m.group(1).strip(), params

        # limit  \lim_{x \to a} ...
        m = re.search(
            r"\\lim_\{?\s*([a-z])\s*(?:\\to|\\rightarrow|->)\s*([^{}]+?)\s*\}?\s*(.*)",
            latex, re.DOTALL,
        )
        if m:
            params.setdefault("variable", m.group(1))
            params["point"] = m.group(2).strip()
            return m.group(3).strip(), params

        # plain limit lim_(x -> a) ... / lim_{x -> a} ... / lim x->a ...
        m = re.search(
            r"\blim_\s*[\(\{\[]\s*([a-z])\s*(?:->|→|to)\s*([^\)\}\]\s]+)\s*[\)\}\]]\s*(.*)",
            latex, re.DOTALL,
        )
        if m:
            params.setdefault("variable", m.group(1))
            params["point"] = m.group(2).strip()
            return m.group(3).strip(), params

        m = re.search(
            r"\blim_?\{?\s*([a-z])\s*(?:->|→|to)\s*([^{} ]+)\s*\}?\s*(.*)",
            latex, re.DOTALL,
        )
        if m:
            params.setdefault("variable", m.group(1))
            params["point"] = m.group(2).strip()
            return m.group(3).strip(), params

        m = re.search(
            r"\blim\s+([a-z])\s*(?:->|→|to)\s*([^\s]+)\s*(.*)",
            latex, re.DOTALL,
        )
        if m:
            params.setdefault("variable", m.group(1))
            params["point"] = m.group(2).strip()
            return m.group(3).strip(), params

        # sum  \sum_{n=a}^{b} ...
        m = re.search(
            r"\\sum_\{?\s*([a-z])=([^{}]*?)\}?\^\{?([^{}]*?)\}?\s*(.*)",
            latex, re.DOTALL,
        )
        if m:
            params.setdefault("variable", m.group(1))
            params["lower"] = self._parse_bound(m.group(2))
            params["upper"] = self._parse_bound(m.group(3))
            return m.group(4).strip(), params

        return latex, params

    @staticmethod
    def _parse_bound(s: str):
        s = s.strip().replace(" ", "")
        if s in ("\\infty", "+\\infty", "oo", "+oo", "∞", "+∞"):
            return "oo"
        if s in ("-\\infty", "-oo", "-∞"):
            return "-oo"
        try:
            return float(s) if "." in s else int(s)
        except ValueError:
            return s
