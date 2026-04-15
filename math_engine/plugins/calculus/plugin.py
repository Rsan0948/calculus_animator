"""CalculusPlugin — adapter wrapping the existing calculus solver pipeline."""

from typing import Any

from engine.state import FormalizedProblem, MathResult, MathStep, VisualHint
from math_engine.base_plugin import MathPlugin
from math_engine.plugins.calculus.animation_engine import AnimationEngine
from math_engine.plugins.calculus.detector import TypeDetector
from math_engine.plugins.calculus.extractor import ExpressionExtractor
from math_engine.plugins.calculus.parser import ExpressionParser
from math_engine.plugins.calculus.solver import CalculusSolver
from math_engine.plugins.calculus.step_generator import StepGenerator


class CalculusPlugin(MathPlugin):
    """Routes calculus problems through the legacy SymPy pipeline."""

    def __init__(self) -> None:
        self._parser = ExpressionParser()
        self._extractor = ExpressionExtractor()
        self._detector = TypeDetector()
        self._solver = CalculusSolver()
        self._step_gen = StepGenerator()
        self._animator = AnimationEngine()

    @property
    def name(self) -> str:
        return "calculus"

    @property
    def supported_domains(self) -> list[str]:
        return [
            "calculus",
            "derivative",
            "integral",
            "limit",
            "series",
            "differential_equation",
            "simplification",
        ]

    def can_solve(self, problem: FormalizedProblem) -> float:
        """High confidence if domain_tags mention calculus or known operations."""
        tags = {t.lower() for t in problem.domain_tags}
        if tags & set(self.supported_domains):
            return 1.0
        # Weak heuristic: if the objective looks like LaTeX with calculus notation
        obj = problem.objective.lower()
        if any(k in obj for k in ("\\frac{d", "\\int", "\\lim", "\\sum")):
            return 0.8
        return 0.0

    def solve(self, problem: FormalizedProblem) -> MathResult:
        """Run the full calculus pipeline.

        Expects the objective field to contain the raw LaTeX expression.
        Optional params can be stashed in problem.metadata['calculus_params'].
        """
        latex_str = problem.objective
        params_dict = problem.metadata.get("calculus_params", {})

        try:
            detected = self._detector.detect(latex_str)
            inner_latex, merged = self._extractor.extract(latex_str, None, params_dict)
            parsed = self._parser.parse(inner_latex or latex_str)

            if not parsed.get("success"):
                return MathResult(
                    problem_id=problem.id,
                    plugin_used=self.name,
                    success=False,
                    failure_reason={
                        "code": "parse_error",
                        "message": parsed.get("error", "Parse failed"),
                        "plugin_used": self.name,
                    },
                )

            expr = parsed["sympy_expr"]
            raw_result = self._solver.solve(expr, detected, merged)

            if not raw_result.get("success"):
                return MathResult(
                    problem_id=problem.id,
                    plugin_used=self.name,
                    success=False,
                    failure_reason={
                        "code": "plugin_error",
                        "message": raw_result.get("error", "Solver failed"),
                        "plugin_used": self.name,
                    },
                )

            # Convert raw steps to MathStep schema
            math_steps: list[MathStep] = []
            for idx, s in enumerate(raw_result.get("steps", []), start=1):
                math_steps.append(
                    MathStep(
                        step_number=idx,
                        title=s.get("rule", "").replace("_", " ").title(),
                        description=s.get("description", ""),
                        before_latex=s.get("before"),
                        after_latex=s.get("after"),
                        rule_applied=s.get("rule"),
                    )
                )

            # Animation steps as visual hints on the final step
            anim_steps = self._step_gen.generate(raw_result, detected)
            if anim_steps:
                math_steps[-1].visual_hints.append(
                    VisualHint(
                        kind="graph",
                        payload={
                            "animation_steps": [a.to_dict() for a in anim_steps],
                            "detected_type": detected.name,
                        },
                    )
                )

            # Graph data
            _single_graph: dict[str, Any] | None = None
            try:
                gd = self._animator.generate_graph_data(expr)
                if gd.get("success"):
                    _single_graph = gd
            except Exception as exc:
                import logging
                logging.getLogger(__name__).debug("Graph generation failed: %s", exc)

            return MathResult(
                problem_id=problem.id,
                plugin_used=self.name,
                success=True,
                final_answer=str(raw_result.get("result", "")),
                steps=math_steps,
                graph_data=[_single_graph] if _single_graph is not None else None,
                metadata={
                    "detected_type": detected.name,
                    "variables": parsed.get("variables", []),
                },
            )
        except Exception as exc:
            return MathResult(
                problem_id=problem.id,
                plugin_used=self.name,
                success=False,
                failure_reason={
                    "code": "plugin_error",
                    "message": str(exc),
                    "plugin_used": self.name,
                },
            )
