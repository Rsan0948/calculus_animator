import re
from enum import Enum, auto
from typing import Optional


class CalculusType(Enum):
    DERIVATIVE = auto()
    INTEGRAL_INDEFINITE = auto()
    INTEGRAL_DEFINITE = auto()
    LIMIT = auto()
    SERIES = auto()
    TAYLOR_SERIES = auto()
    DIFFERENTIAL_EQ = auto()
    SIMPLIFY = auto()
    UNKNOWN = auto()


_TAG_MAP = {
    "derivative": CalculusType.DERIVATIVE,
    "integral": CalculusType.INTEGRAL_INDEFINITE,
    "definite_integral": CalculusType.INTEGRAL_DEFINITE,
    "limit": CalculusType.LIMIT,
    "series": CalculusType.SERIES,
    "taylor": CalculusType.TAYLOR_SERIES,
    "ode": CalculusType.DIFFERENTIAL_EQ,
}

# Order matters — check definite integral before indefinite
_PATTERNS = [
    (CalculusType.DIFFERENTIAL_EQ, [
        r"\\frac\{dy\}\{dx\}\s*=", r"y''\s*[+\-=]", r"y'\s*[+\-=]",
        r"(?i)solve\s+the\s+ode",
    ]),
    (CalculusType.DERIVATIVE, [
        r"\\frac\{d", r"\\frac\{\\partial", r"'",
        r"\bd(?:\^\d+)?\s*/\s*d[a-z](?:\^\d+)?\b",
        r"(?i)\bderivative\b", r"(?i)\bdifferentiate\b",
    ]),
    (CalculusType.INTEGRAL_DEFINITE, [
        r"\\int_", r"\bint_", r"∫_",
        r"(?i)definite\s+integral",
    ]),
    (CalculusType.INTEGRAL_INDEFINITE, [
        r"\\int", r"\bint\b", r"∫",
        r"(?i)\bintegral\b", r"(?i)\bintegrate\b", r"(?i)\bantiderivative\b",
    ]),
    (CalculusType.LIMIT, [
        r"\\lim", r"\blim\b", r"\blim_", r"\blim\s*[\(\{]",
        r"(?i)\blimit\b",
    ]),
    (CalculusType.SERIES, [
        r"\\sum", r"\\prod",
        r"(?i)\bsum\b",
    ]),
    (CalculusType.TAYLOR_SERIES, [
        r"(?i)taylor", r"(?i)maclaurin",
    ]),
]


class TypeDetector:
    def detect(self, latex: str, explicit_tag: Optional[str] = None) -> CalculusType:
        """Detect the calculus operation type from a LaTeX string.

        Pattern matching is ordered so that more specific forms (e.g. definite
        integral) are checked before generic ones (indefinite integral).
        Falls back to ``SIMPLIFY`` when no pattern matches.

        Args:
            latex: The raw LaTeX expression to inspect.
            explicit_tag: Optional string override (e.g. ``"derivative"``,
                ``"definite_integral"``).  When provided, regex scanning is
                skipped entirely.

        Returns:
            A ``CalculusType`` enum member representing the detected operation.
        """
        if explicit_tag:
            return _TAG_MAP.get(explicit_tag.lower(), CalculusType.UNKNOWN)
        for calc_type, patterns in _PATTERNS:
            for p in patterns:
                if re.search(p, latex):
                    return calc_type
        return CalculusType.SIMPLIFY
