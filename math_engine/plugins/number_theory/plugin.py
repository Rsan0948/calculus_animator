"""Number Theory Plugin — number-theoretic computations using SymPy."""

import logging
import re
from typing import List, Tuple

import sympy
from sympy import ntheory

from engine.state import FormalizedProblem, MathResult, MathStep
from math_engine.base_plugin import MathPlugin

logger = logging.getLogger(__name__)


class NumberTheoryPlugin(MathPlugin):
    """Plugin for number theory: primes, factorization, modular arithmetic."""

    @property
    def name(self) -> str:
        return "number_theory"

    @property
    def supported_domains(self) -> list[str]:
        return ["number_theory", "primes", "modular_arithmetic", "factorization", "gcd", "lcm"]

    def can_solve(self, problem: FormalizedProblem) -> float:
        tags = {t.lower() for t in problem.domain_tags}
        if tags & set(self.supported_domains):
            return 1.0
        obj = problem.objective.lower()
        keywords = ["prime", "factor", "gcd", "lcm", "modular", "diophantine", "totient", "phi"]
        return 0.9 if any(kw in obj for kw in keywords) else 0.0

    def solve(self, problem: FormalizedProblem) -> MathResult:
        try:
            obj = problem.objective.lower()
            op = self._detect_operation(obj)
            return getattr(self, f"_{op}")(problem)
        except Exception as e:
            logger.exception("Number theory solve failed")
            return self._error_result(problem, e)

    def _detect_operation(self, obj: str) -> str:
        if "is_prime" in obj or "prime?" in obj:
            return "is_prime"
        if "next_prime" in obj:
            return "next_prime"
        if "factor" in obj:
            return "prime_factorization"
        if "divisor_count" in obj:
            return "divisor_count"
        if "divisor" in obj:
            return "divisors"
        if "gcd" in obj:
            return "gcd"
        if "lcm" in obj:
            return "lcm"
        if "totient" in obj or "phi" in obj:
            return "euler_totient"
        if "modular_inverse" in obj:
            return "modular_inverse"
        if "modular_pow" in obj or "modular_exponentiation" in obj:
            return "modular_exponentiation"
        if "prime" in obj:
            return "is_prime"
        return "is_prime"

    def _parse_integers(self, text: str, count: int = 2) -> List[int]:
        nums = [int(n) for n in re.findall(r'-?\d+', text)]
        defaults = [100, 10, 2][:count]
        return nums[:count] if len(nums) >= count else defaults

    def _is_prime(self, problem: FormalizedProblem) -> MathResult:
        n = self._parse_integers(problem.objective, 1)[0]
        result = sympy.isprime(n)
        return MathResult(
            problem_id=problem.id, plugin_used=self.name, success=True,
            final_answer=f"{n} is {'prime' if result else 'not prime'}",
            steps=[MathStep(step_number=1, title="Prime Check", description=f"{n} is {'prime' if result else 'composite'}")],
            metadata={"operation": "is_prime", "n": n, "result": result}
        )

    def _next_prime(self, problem: FormalizedProblem) -> MathResult:
        n = self._parse_integers(problem.objective, 1)[0]
        result = sympy.nextprime(n)
        return MathResult(
            problem_id=problem.id, plugin_used=self.name, success=True,
            final_answer=f"Next prime after {n} is {result}",
            steps=[MathStep(step_number=1, title="Next Prime", description=f"Next prime after {n} = {result}")],
            metadata={"operation": "next_prime", "n": n, "result": int(result)}
        )

    def _prime_factorization(self, problem: FormalizedProblem) -> MathResult:
        n = abs(self._parse_integers(problem.objective, 1)[0])
        factors = sympy.factorint(n)
        factor_str = " × ".join(f"{p}^{e}" if e > 1 else str(p) for p, e in factors.items())
        return MathResult(
            problem_id=problem.id, plugin_used=self.name, success=True,
            final_answer=f"{n} = {factor_str}",
            steps=[MathStep(step_number=1, title="Factorization", description=f"{n} = {factor_str}")],
            metadata={"operation": "prime_factorization", "n": n, "factors": factors}
        )

    def _divisors(self, problem: FormalizedProblem) -> MathResult:
        n = self._parse_integers(problem.objective, 1)[0]
        divs = sympy.divisors(n)
        return MathResult(
            problem_id=problem.id, plugin_used=self.name, success=True,
            final_answer=f"Divisors of {n}: {divs}",
            steps=[MathStep(step_number=1, title="Divisors", description=f"Divisors of {n}: {divs}")],
            metadata={"operation": "divisors", "n": n, "divisors": divs}
        )

    def _divisor_count(self, problem: FormalizedProblem) -> MathResult:
        n = self._parse_integers(problem.objective, 1)[0]
        result = sympy.divisor_count(n)
        return MathResult(
            problem_id=problem.id, plugin_used=self.name, success=True,
            final_answer=f"d({n}) = {result}",
            steps=[MathStep(step_number=1, title="Divisor Count", description=f"d({n}) = {result}")],
            metadata={"operation": "divisor_count", "n": n, "result": result}
        )

    def _gcd(self, problem: FormalizedProblem) -> MathResult:
        nums = self._parse_integers(problem.objective, 2)
        a, b = nums[0], nums[1] if len(nums) > 1 else 18
        result = sympy.gcd(a, b)
        return MathResult(
            problem_id=problem.id, plugin_used=self.name, success=True,
            final_answer=f"gcd({a}, {b}) = {result}",
            steps=[MathStep(step_number=1, title="GCD", description=f"gcd({a}, {b}) = {result}")],
            metadata={"operation": "gcd", "numbers": [a, b], "result": int(result)}
        )

    def _lcm(self, problem: FormalizedProblem) -> MathResult:
        nums = self._parse_integers(problem.objective, 2)
        a, b = nums[0], nums[1] if len(nums) > 1 else 6
        result = sympy.lcm(a, b)
        return MathResult(
            problem_id=problem.id, plugin_used=self.name, success=True,
            final_answer=f"lcm({a}, {b}) = {result}",
            steps=[MathStep(step_number=1, title="LCM", description=f"lcm({a}, {b}) = {result}")],
            metadata={"operation": "lcm", "numbers": [a, b], "result": int(result)}
        )

    def _euler_totient(self, problem: FormalizedProblem) -> MathResult:
        n = self._parse_integers(problem.objective, 1)[0]
        result = sympy.totient(n)
        return MathResult(
            problem_id=problem.id, plugin_used=self.name, success=True,
            final_answer=f"φ({n}) = {result}",
            steps=[MathStep(step_number=1, title="Euler's Totient", description=f"φ({n}) = {result}")],
            metadata={"operation": "euler_totient", "n": n, "result": int(result)}
        )

    def _modular_inverse(self, problem: FormalizedProblem) -> MathResult:
        nums = self._parse_integers(problem.objective, 2)
        a, m = nums[0], nums[1] if len(nums) > 1 else 17
        try:
            result = sympy.mod_inverse(a, m)
            return MathResult(
                problem_id=problem.id, plugin_used=self.name, success=True,
                final_answer=f"{a}⁻¹ ≡ {result} (mod {m})",
                steps=[MathStep(step_number=1, title="Modular Inverse", description=f"{a}⁻¹ ≡ {result} (mod {m})")],
                metadata={"operation": "modular_inverse", "a": a, "m": m, "result": int(result)}
            )
        except ValueError:
            return self._error(problem, "no_inverse", f"No inverse exists for {a} mod {m}")

    def _modular_exponentiation(self, problem: FormalizedProblem) -> MathResult:
        nums = self._parse_integers(problem.objective, 3)
        base, exp, mod = nums[0], nums[1] if len(nums) > 1 else 10, nums[2] if len(nums) > 2 else 1000
        result = pow(base, exp, mod)
        return MathResult(
            problem_id=problem.id, plugin_used=self.name, success=True,
            final_answer=f"{base}^{exp} ≡ {result} (mod {mod})",
            steps=[MathStep(step_number=1, title="Modular Exponentiation", description=f"{base}^{exp} ≡ {result} (mod {mod})")],
            metadata={"operation": "modular_exponentiation", "base": base, "exp": exp, "mod": mod, "result": result}
        )

    def _error(self, problem: FormalizedProblem, code: str, msg: str) -> MathResult:
        return MathResult(problem_id=problem.id, plugin_used=self.name, success=False,
                         failure_reason={"code": code, "message": msg, "plugin_used": self.name})

    def _error_result(self, problem: FormalizedProblem, error: Exception) -> MathResult:
        return MathResult(problem_id=problem.id, plugin_used=self.name, success=False,
                         failure_reason={"code": "computation_error", "message": str(error), "plugin_used": self.name})
