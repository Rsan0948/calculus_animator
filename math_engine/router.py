"""Router that selects the best MathPlugin for a given FormalizedProblem."""

import json
import logging
from copy import deepcopy
from typing import Any, Optional

from engine.state import FormalizedProblem, MathResult
from engine.state_manager import StateManager
from math_engine.base_plugin import MathPlugin
from math_engine.input_parser import InputParser

logger = logging.getLogger(__name__)


class Router:
    """Selects and invokes the appropriate math plugin for a problem."""

    def __init__(self, state_manager: Optional[StateManager] = None) -> None:
        self._plugins: list[MathPlugin] = []
        self._input_parser = InputParser()
        self.state_manager = state_manager

    def register(self, plugin: MathPlugin) -> None:
        """Add a plugin to the routing table."""
        self._plugins.append(plugin)
        logger.info("Registered math plugin: %s", plugin.name)

    def analyze(self, problem: FormalizedProblem) -> dict[str, Any]:
        """Describe the routing decision without executing the plugin."""
        if not self._plugins:
            return {
                "success": False,
                "selected_plugin": None,
                "selected_score": 0.0,
                "scores": [],
                "normalized_objective": problem.objective,
                "preparsed": False,
                "failure_reason": {
                    "code": "unsupported_domain",
                    "message": "No math plugins are registered.",
                    "plugin_used": None,
                },
            }

        scored = [(plugin, plugin.can_solve(problem)) for plugin in self._plugins]
        scored.sort(key=lambda item: item[1], reverse=True)
        best_plugin, best_score = scored[0]

        score_rows = [
            {"plugin": plugin.name, "score": score}
            for plugin, score in scored
        ]

        if best_score < 0.1:
            domains = ", ".join(problem.domain_tags) or "unknown"
            available = ", ".join(plugin.name for plugin in self._plugins)
            return {
                "success": False,
                "selected_plugin": None,
                "selected_score": best_score,
                "scores": score_rows,
                "normalized_objective": problem.objective,
                "preparsed": False,
                "failure_reason": {
                    "code": "unsupported_domain",
                    "message": (
                        f"No plugin confident for domains '{domains}'. "
                        f"Available plugins: {available}"
                    ),
                    "plugin_used": None,
                },
            }

        normalized_objective = problem.objective
        was_preparsed = False
        plugins_with_own_parser = {"calculus"}

        if best_plugin.name not in plugins_with_own_parser and not self._is_structured(problem.objective):
            logger.debug("Pre-parsing natural language input for %s", best_plugin.name)
            parsed_input = self._input_parser.parse_for_domain(
                problem.objective,
                best_plugin.supported_domains[0],
            )
            normalized_objective = json.dumps(parsed_input)
            was_preparsed = True

        return {
            "success": True,
            "selected_plugin": best_plugin.name,
            "selected_score": best_score,
            "scores": score_rows,
            "normalized_objective": normalized_objective,
            "preparsed": was_preparsed,
            "failure_reason": None,
        }

    def solve_with_analysis(
        self,
        problem: FormalizedProblem,
        analysis: Optional[dict[str, Any]] = None,
    ) -> MathResult:
        """Solve a problem using a precomputed routing decision."""
        routing = analysis or self.analyze(problem)
        if not routing.get("success"):
            failure_reason = routing.get("failure_reason") or {
                "code": "unsupported_domain",
                "message": "No plugin confident for this problem.",
                "plugin_used": None,
            }
            return MathResult(
                problem_id=problem.id,
                plugin_used="none",
                success=False,
                failure_reason=failure_reason,
            )

        plugin_name = str(routing["selected_plugin"])
        plugin = self._get_plugin(plugin_name)
        if plugin is None:
            return MathResult(
                problem_id=problem.id,
                plugin_used="none",
                success=False,
                failure_reason={
                    "code": "plugin_not_registered",
                    "message": f"Selected plugin '{plugin_name}' is not registered.",
                    "plugin_used": plugin_name,
                },
            )

        normalized_problem = deepcopy(problem)
        normalized_problem.objective = str(routing.get("normalized_objective", problem.objective))

        logger.info(
            "Routing problem %s to plugin %s (confidence=%.2f)",
            problem.id,
            plugin.name,
            float(routing.get("selected_score", 0.0)),
        )
        result = plugin.solve(normalized_problem)

        if self.state_manager:
            self.state_manager.save_math_result(problem.id, result)

        return result

    def route(self, problem: FormalizedProblem) -> MathResult:
        """Find the best plugin and solve the problem."""
        return self.solve_with_analysis(problem, self.analyze(problem))

    def _get_plugin(self, plugin_name: str) -> MathPlugin | None:
        for plugin in self._plugins:
            if plugin.name == plugin_name:
                return plugin
        return None

    def _is_structured(self, objective: str) -> bool:
        """Check if objective is already structured JSON."""
        try:
            json.loads(objective)
            return True
        except json.JSONDecodeError:
            return False
