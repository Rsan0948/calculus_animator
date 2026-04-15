"""Logic Plugin — boolean logic and SAT solving using SymPy."""

import json
import logging
import re
from typing import List, Tuple, Any

import sympy
from sympy import symbols, Or, And, Not, Implies, Equivalent
from sympy.logic import simplify_logic
from sympy.logic.inference import satisfiable

from engine.state import FormalizedProblem, MathResult, MathStep
from math_engine.base_plugin import MathPlugin
from math_engine.input_parser import InputParser

logger = logging.getLogger(__name__)


class LogicPlugin(MathPlugin):
    """Plugin for logic: boolean algebra, SAT solving, propositional logic."""

    @property
    def name(self) -> str:
        return "logic"

    @property
    def supported_domains(self) -> List[str]:
        return ["logic"]

    def can_solve(self, problem: FormalizedProblem) -> float:
        """Score based on logic keywords and variables."""
        if "logic" in problem.domain_tags:
            return 1.0
        
        # Keywords
        logic_keywords = ["boolean", "sat", "satisfiable", "truth table", "proposition", "simplify"]
        if any(kw in problem.objective.lower() for kw in logic_keywords):
            return 0.8
            
        return 0.0

    def solve(self, problem: FormalizedProblem) -> MathResult:
        """Route to specific logic solver."""
        try:
            # Parse input
            try:
                data = json.loads(problem.objective)
                operation = data.get("operation", "simplify")
                expr_str = data.get("expression", "")
                variables = data.get("variables", [])
            except json.JSONDecodeError:
                parsed = InputParser().parse_for_domain(problem.objective, self.name)
                operation = str(parsed.get("operation") or "simplify")
                expr_str = str(parsed.get("expression") or problem.objective)
                variables = list(parsed.get("variables") or sorted(set(re.findall(r'\b[a-zA-Z]\b', expr_str))))

            # Parse to SymPy
            expr = self._parse_expression(expr_str, variables)
            
            if operation == "satisfiable":
                return self._solve_satisfiable(problem, expr)
            else:
                return self._solve_simplify(problem, expr)

        except Exception as e:
            logger.error("Logic solver failed: %s", e)
            return MathResult(
                problem_id=problem.id,
                plugin_used=self.name,
                success=False,
                failure_reason={
                    "code": "logic_error",
                    "message": str(e),
                    "plugin_used": self.name
                }
            )

    def _parse_expression(self, expr_str: str, var_names: List[str]):
        """Convert string expression to SymPy logic object."""
        # Create symbols
        if not var_names:
            var_names = ['p', 'q']
        
        symbols_dict = {name: symbols(name) for name in var_names}
        
        # Basic normalization
        normalized = expr_str.replace("^", " & ").replace("+", " | ").replace("!", " ~ ")
        normalized = re.sub(r'\band\b', ' & ', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\bor\b', ' | ', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\bnot\b', ' ~ ', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\bimplies\b', ' >> ', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\bequiv\b', ' == ', normalized, flags=re.IGNORECASE)
        
        # Normalize parentheses spacing
        normalized = normalized.replace("(", " ( ").replace(")", " ) ")
        
        # Clean up multiple spaces
        normalized = ' '.join(normalized.split())
        
        # Safely evaluate using sympify instead of eval
        allowed_names = {
            **symbols_dict,
            'And': And, 'Or': Or, 'Not': Not,
            'Implies': Implies, 'Equivalent': Equivalent
        }
        
        if not normalized:
            raise ValueError("Logic expression is empty")

        try:
            return sympy.sympify(normalized, locals=allowed_names, evaluate=False)
        except Exception as e:
            logger.warning("Failed to parse expression '%s': %s", expr_str, e)
            raise ValueError(f"Could not parse logic expression: {expr_str}") from e

    def _solve_simplify(self, problem: FormalizedProblem, expr) -> MathResult:
        """Simplify boolean expression."""
        simplified = simplify_logic(expr)
        
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer=str(simplified),
            steps=[
                MathStep(
                    step_number=1,
                    title="Simplification",
                    description=f"Simplified {expr} using boolean algebra rules",
                    before_latex=str(expr),
                    after_latex=str(simplified),
                    rule_applied="boolean_simplification"
                )
            ]
        )

    def _solve_satisfiable(self, problem: FormalizedProblem, expr) -> MathResult:
        """Check if expression is satisfiable."""
        result = satisfiable(expr)
        
        if result:
            answer = f"Satisfiable with: {result}"
            success = True
        else:
            answer = "Unsatisfiable"
            success = True # Computation succeeded even if unsat
            
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=success,
            final_answer=answer,
            steps=[
                MathStep(
                    step_number=1,
                    title="SAT Solving",
                    description=f"Checked satisfiability of {expr}",
                    before_latex=str(expr),
                    after_latex=answer,
                    rule_applied="dpll_algorithm"
                )
            ]
        )
