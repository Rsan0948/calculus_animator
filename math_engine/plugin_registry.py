"""Math plugin registry and support metadata."""

import logging
from typing import TypedDict

from math_engine.base_plugin import MathPlugin
from math_engine.plugins.calculus.plugin import CalculusPlugin
from math_engine.plugins.combinatorics.plugin import CombinatoricsPlugin
from math_engine.plugins.graph_theory.plugin import GraphTheoryPlugin
from math_engine.plugins.linear_algebra.plugin import LinearAlgebraPlugin
from math_engine.plugins.logic.plugin import LogicPlugin
from math_engine.plugins.number_theory.plugin import NumberTheoryPlugin
from math_engine.plugins.optimization.plugin import OptimizationPlugin
from math_engine.plugins.statistics.plugin import StatisticsPlugin

logger = logging.getLogger(__name__)


class PluginSupportInfo(TypedDict):
    """Support metadata for a registered plugin."""

    status: str
    summary: str
    recommended_input: str


AVAILABLE_PLUGINS: list[type[MathPlugin]] = [
    CalculusPlugin,
    LinearAlgebraPlugin,
    StatisticsPlugin,
    OptimizationPlugin,
    NumberTheoryPlugin,
    CombinatoricsPlugin,
    GraphTheoryPlugin,
    LogicPlugin,
]

PLUGIN_SUPPORT: dict[str, PluginSupportInfo] = {
    "calculus": {
        "status": "reliable",
        "summary": "Strongest end-to-end domain with the most mature solving pipeline.",
        "recommended_input": "Natural language or LaTeX calculus expressions.",
    },
    "linear_algebra": {
        "status": "beta",
        "summary": "Core operations work, but structured inputs are preferred for consistency.",
        "recommended_input": "Natural language for common cases or structured JSON for precise control.",
    },
    "statistics": {
        "status": "beta",
        "summary": "Summary statistics and common tests work, with stricter structured input handling.",
        "recommended_input": "Natural language for common summaries or structured JSON for paired data/tests.",
    },
    "optimization": {
        "status": "experimental",
        "summary": "Current solver path is example-driven and not yet reliable for arbitrary objectives.",
        "recommended_input": "Treat as exploratory only; do not rely on it for production workflows.",
    },
    "number_theory": {
        "status": "reliable",
        "summary": "Simple arithmetic and prime-related flows are stable on the CLI path.",
        "recommended_input": "Natural language number theory prompts.",
    },
    "combinatorics": {
        "status": "beta",
        "summary": "Common counting operations work, but broader coverage still needs tightening.",
        "recommended_input": "Natural language prompts with explicit integers.",
    },
    "graph_theory": {
        "status": "beta",
        "summary": "Shortest-path style examples work, but graph modeling remains limited.",
        "recommended_input": "Simple natural language shortest-path prompts or structured graph JSON.",
    },
    "logic": {
        "status": "reliable",
        "summary": "Boolean simplification and satisfiability flows are stable on the golden path.",
        "recommended_input": "Natural language or compact symbolic logic expressions.",
    },
}


def register_all_plugins(router) -> None:
    """Register all available plugins with the router."""
    for plugin_class in AVAILABLE_PLUGINS:
        try:
            plugin = plugin_class()
            router.register(plugin)
        except Exception as exc:
            logger.warning("Failed to register plugin %s: %s", plugin_class.__name__, exc)

    logger.info("Registered %d math plugins", len(router._plugins))


def get_available_domains() -> list[str]:
    """Get list of all available math domains."""
    domains = set()
    for plugin_class in AVAILABLE_PLUGINS:
        try:
            plugin = plugin_class()
            domains.update(plugin.supported_domains)
        except Exception:
            continue
    return sorted(domains)


def get_plugin_capabilities() -> dict[str, dict[str, str | list[str]]]:
    """Get capabilities and support metadata for all available plugins."""
    capabilities: dict[str, dict[str, str | list[str]]] = {}
    for plugin_class in AVAILABLE_PLUGINS:
        try:
            plugin = plugin_class()
            support = PLUGIN_SUPPORT.get(
                plugin.name,
                {
                    "status": "unknown",
                    "summary": "No support metadata recorded.",
                    "recommended_input": "Unknown",
                },
            )
            capabilities[plugin.name] = {
                "domains": plugin.supported_domains,
                "description": plugin.__doc__ or "No description",
                "status": support["status"],
                "summary": support["summary"],
                "recommended_input": support["recommended_input"],
            }
        except Exception as exc:
            capabilities[plugin_class.__name__] = {"error": str(exc)}
    return capabilities
