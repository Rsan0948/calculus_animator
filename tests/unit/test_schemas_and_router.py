"""Phase 0 unit tests for core schemas and the math engine router."""

from engine.state import FormalizedProblem, MathResult, SourceDocument
from math_engine.plugins.calculus.plugin import CalculusPlugin
from math_engine.router import Router


def test_formalized_problem_defaults() -> None:
    problem = FormalizedProblem(
        source_document=SourceDocument(format="pdf"),
        title="Test",
        domain_tags=["calculus"],
        objective="x^2",
    )
    assert problem.title == "Test"
    assert problem.domain_tags == ["calculus"]
    assert problem.confidence == 0.0


def test_router_no_plugins() -> None:
    router = Router()
    problem = FormalizedProblem(
        source_document=SourceDocument(),
        title="No plugins",
        domain_tags=["unknown"],
        objective="x^2",
    )
    result = router.route(problem)
    assert result.success is False
    assert result.failure_reason is not None
    assert result.failure_reason["code"] == "unsupported_domain"


def test_calculus_plugin_can_solve() -> None:
    plugin = CalculusPlugin()
    problem = FormalizedProblem(
        source_document=SourceDocument(),
        title="Derivative",
        domain_tags=["calculus"],
        objective="\\frac{d}{dx} x^3",
    )
    assert plugin.can_solve(problem) == 1.0


def test_calculus_plugin_solves_derivative() -> None:
    plugin = CalculusPlugin()
    problem = FormalizedProblem(
        source_document=SourceDocument(),
        title="Derivative",
        domain_tags=["calculus"],
        objective="\\frac{d}{dx} x^3",
    )
    result = plugin.solve(problem)
    assert result.success is True
    assert result.final_answer == "3*x**2"
    assert result.plugin_used == "calculus"
    assert len(result.steps) >= 1


def test_router_with_calculus_plugin() -> None:
    router = Router()
    router.register(CalculusPlugin())
    problem = FormalizedProblem(
        source_document=SourceDocument(),
        title="Integral",
        domain_tags=["calculus"],
        objective="\\int x^2 \\, dx",
    )
    result = router.route(problem)
    assert result.success is True
    assert result.plugin_used == "calculus"


def test_math_result_serialization() -> None:
    result = MathResult(
        problem_id="123",
        plugin_used="test",
        success=True,
        final_answer="42",
    )
    data = result.model_dump()
    assert data["success"] is True
    assert data["final_answer"] == "42"
