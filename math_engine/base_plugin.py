"""Abstract base class for all math engine plugins."""


from abc import ABC, abstractmethod

from engine.state import FormalizedProblem, MathResult


class MathPlugin(ABC):
    """Contract for a domain-specific mathematical solver."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable plugin identifier."""
        ...

    @property
    @abstractmethod
    def supported_domains(self) -> list[str]:
        """Domain tags this plugin can handle (e.g., ['calculus', 'derivatives'])."""
        ...

    @abstractmethod
    def can_solve(self, problem: FormalizedProblem) -> float:
        """Return confidence score in [0.0, 1.0].

        1.0 means this plugin is the definitive solver for the problem.
        0.0 means it cannot handle the problem at all.
        """
        ...

    @abstractmethod
    def solve(self, problem: FormalizedProblem) -> MathResult:
        """Attempt to solve the problem.

        Must return a MathResult. On failure, set success=False and populate
        failure_reason.
        """
        ...
