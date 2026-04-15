"""Combinatorics Plugin — counting, permutations, combinations, partitions."""

import logging
import re
from typing import List

import sympy

from engine.state import FormalizedProblem, MathResult, MathStep
from math_engine.base_plugin import MathPlugin

logger = logging.getLogger(__name__)


class CombinatoricsPlugin(MathPlugin):
    """Plugin for combinatorics: permutations, combinations, partitions."""

    @property
    def name(self) -> str:
        return "combinatorics"

    @property
    def supported_domains(self) -> list[str]:
        return ["combinatorics", "counting", "permutations", "combinations", "partitions", "binomial_coefficients"]

    def can_solve(self, problem: FormalizedProblem) -> float:
        tags = {t.lower() for t in problem.domain_tags}
        if tags & set(self.supported_domains):
            return 1.0
        obj = problem.objective.lower()
        keywords = ["permutation", "combination", "binomial", "factorial", "catalan", "bell", "stirling", "partition"]
        return 0.9 if any(kw in obj for kw in keywords) else 0.0

    def solve(self, problem: FormalizedProblem) -> MathResult:
        try:
            obj = problem.objective.lower()
            op = self._detect_operation(obj)
            return getattr(self, f"_{op}")(problem)
        except Exception as e:
            logger.exception("Combinatorics solve failed")
            return self._error_result(problem, e)

    def _detect_operation(self, obj: str) -> str:
        if "factorial" in obj or "n!" in obj:
            return "factorial"
        if "permutation" in obj:
            return "permutations"
        if "combination" in obj and "multinomial" not in obj:
            return "combinations"
        if "catalan" in obj:
            return "catalan"
        if "bell" in obj:
            return "bell_number"
        if "stirling" in obj:
            return "stirling2"
        if "partition" in obj:
            return "partition"
        return "binomial_coefficient"

    def _parse_integers(self, text: str, count: int = 2) -> List[int]:
        nums = [int(n) for n in re.findall(r'\d+', text)]
        return nums[:count] if len(nums) >= count else ([5] if count == 1 else [5, 3])

    def _factorial(self, problem: FormalizedProblem) -> MathResult:
        n = self._parse_integers(problem.objective, 1)[0]
        result = sympy.factorial(n)
        return MathResult(
            problem_id=problem.id, plugin_used=self.name, success=True,
            final_answer=f"{n}! = {result}",
            steps=[MathStep(step_number=1, title="Factorial", description=f"{n}! = {result}")],
            metadata={"operation": "factorial", "n": n, "result": int(result)}
        )

    def _permutations(self, problem: FormalizedProblem) -> MathResult:
        n, k = self._parse_integers(problem.objective, 2)
        result = sympy.FallingFactorial(n, k)
        return MathResult(
            problem_id=problem.id, plugin_used=self.name, success=True,
            final_answer=f"P({n}, {k}) = {result}",
            steps=[MathStep(step_number=1, title="Permutations", description=f"P({n}, {k}) = {n}!/({n}-{k})! = {result}")],
            metadata={"operation": "permutations", "n": n, "k": k, "result": int(result)}
        )

    def _combinations(self, problem: FormalizedProblem) -> MathResult:
        n, k = self._parse_integers(problem.objective, 2)
        result = sympy.binomial(n, k)
        return MathResult(
            problem_id=problem.id, plugin_used=self.name, success=True,
            final_answer=f"C({n}, {k}) = {result}",
            steps=[MathStep(step_number=1, title="Combinations", description=f"C({n}, {k}) = ({n} choose {k}) = {result}")],
            metadata={"operation": "combinations", "n": n, "k": k, "result": int(result)}
        )

    def _binomial_coefficient(self, problem: FormalizedProblem) -> MathResult:
        return self._combinations(problem)

    def _catalan(self, problem: FormalizedProblem) -> MathResult:
        n = self._parse_integers(problem.objective, 1)[0]
        result = sympy.catalan(n)
        return MathResult(
            problem_id=problem.id, plugin_used=self.name, success=True,
            final_answer=f"C_{n} = {result}",
            steps=[MathStep(step_number=1, title="Catalan", description=f"C_{n} = (1/(n+1)) × C(2n,n) = {result}")],
            metadata={"operation": "catalan", "n": n, "result": int(result)}
        )

    def _bell_number(self, problem: FormalizedProblem) -> MathResult:
        n = self._parse_integers(problem.objective, 1)[0]
        if n > 50:
            return self._error(problem, "too_large", "Bell numbers grow too fast for n > 50")
        result = sympy.bell(n)
        return MathResult(
            problem_id=problem.id, plugin_used=self.name, success=True,
            final_answer=f"B_{n} = {result}",
            steps=[MathStep(step_number=1, title="Bell Number", description=f"B_{n} = {result}")],
            metadata={"operation": "bell_number", "n": n, "result": int(result)}
        )

    def _stirling2(self, problem: FormalizedProblem) -> MathResult:
        n, k = self._parse_integers(problem.objective, 2)
        result = sympy.stirling2(n, k)
        return MathResult(
            problem_id=problem.id, plugin_used=self.name, success=True,
            final_answer=f"S({n}, {k}) = {result}",
            steps=[MathStep(step_number=1, title="Stirling Number", description=f"S({n}, {k}) = {result}")],
            metadata={"operation": "stirling2", "n": n, "k": k, "result": int(result)}
        )

    def _partition(self, problem: FormalizedProblem) -> MathResult:
        n = self._parse_integers(problem.objective, 1)[0]
        if n > 100:
            return self._error(problem, "too_large", "Use n ≤ 100 for partitions")
        result = sympy.npartitions(n)
        return MathResult(
            problem_id=problem.id, plugin_used=self.name, success=True,
            final_answer=f"p({n}) = {result}",
            steps=[MathStep(step_number=1, title="Partition", description=f"p({n}) = {result}")],
            metadata={"operation": "partition", "n": n, "result": int(result)}
        )

    def _error(self, problem: FormalizedProblem, code: str, msg: str) -> MathResult:
        return MathResult(problem_id=problem.id, plugin_used=self.name, success=False,
                         failure_reason={"code": code, "message": msg, "plugin_used": self.name})

    def _error_result(self, problem: FormalizedProblem, error: Exception) -> MathResult:
        return MathResult(problem_id=problem.id, plugin_used=self.name, success=False,
                         failure_reason={"code": "computation_error", "message": str(error), "plugin_used": self.name})
