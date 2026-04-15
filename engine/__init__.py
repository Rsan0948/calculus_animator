"""Core orchestration and state definitions for the research engine."""

from engine.state import Constraint, ExpectedOutput, FormalizedProblem
from engine.state import GuardrailReport, MathResult, MathStep, MVPOutput
from engine.state import SourceDocument, Variable, VisualHint

__all__ = [
    "Constraint",
    "ExpectedOutput",
    "FormalizedProblem",
    "GuardrailReport",
    "MathResult",
    "MathStep",
    "MVPOutput",
    "SourceDocument",
    "Variable",
    "VisualHint",
]
