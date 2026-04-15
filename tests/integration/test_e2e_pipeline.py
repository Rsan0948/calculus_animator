"""End-to-end integration tests for the full pipeline."""

import tempfile
from pathlib import Path

from engine.state import FormalizedProblem, SourceDocument
from engine.state_manager import StateManager
from math_engine.plugin_registry import register_all_plugins
from math_engine.router import Router


class TestEndToEndPipeline:
    """Test complete pipeline from input to output."""

    def test_solve_calculus_problem(self):
        """End-to-end: Solve a calculus problem through the router."""
        problem = FormalizedProblem(
            id="e2e-calc-test",
            domain_tags=["calculus"],
            objective="\\frac{d}{dx} x^3",
            source_document=SourceDocument(),
        )

        router = Router()
        register_all_plugins(router)
        result = router.route(problem)

        assert result.success
        assert "3" in result.final_answer
        assert result.plugin_used == "calculus"

    def test_solve_linear_algebra_natural_language(self):
        """End-to-end: Parse natural language and solve."""
        problem = FormalizedProblem(
            id="e2e-la-test",
            domain_tags=["linear_algebra"],
            objective="eigenvalues of [[1, 2], [3, 4]]",
            source_document=SourceDocument(),
        )

        router = Router()
        register_all_plugins(router)
        result = router.route(problem)

        assert result.success
        assert result.plugin_used == "linear_algebra"
        assert "eigenvalue" in result.final_answer.lower()

    def test_solve_statistics_problem(self):
        """End-to-end: Solve a statistics problem."""
        problem = FormalizedProblem(
            id="e2e-stats-test",
            domain_tags=["statistics"],
            objective="mean of [1, 2, 3, 4, 5]",
            source_document=SourceDocument(),
        )

        router = Router()
        register_all_plugins(router)
        result = router.route(problem)

        assert result.success
        assert result.plugin_used == "statistics"
        assert "3.0000" in result.final_answer

    def test_solve_number_theory_problem(self):
        """End-to-end: Solve a number theory problem."""
        problem = FormalizedProblem(
            id="e2e-nt-test",
            domain_tags=["number_theory"],
            objective="is 97 prime",
            source_document=SourceDocument(),
        )

        router = Router()
        register_all_plugins(router)
        result = router.route(problem)

        assert result.success
        assert result.plugin_used == "number_theory"
        assert "prime" in result.final_answer.lower()

    def test_solve_combinatorics_problem(self):
        """End-to-end: Solve a combinatorics problem."""
        problem = FormalizedProblem(
            id="e2e-comb-test",
            domain_tags=["combinatorics"],
            objective="combinations of 10 choose 3",
            source_document=SourceDocument(),
        )

        router = Router()
        register_all_plugins(router)
        result = router.route(problem)

        assert result.success
        assert result.plugin_used == "combinatorics"
        assert "120" in result.final_answer

    def test_solve_graph_theory_problem(self):
        """End-to-end: Solve a graph theory problem."""
        problem = FormalizedProblem(
            id="e2e-graph-test",
            domain_tags=["graph_theory"],
            objective="shortest path from A to E",
            source_document=SourceDocument(),
        )

        router = Router()
        register_all_plugins(router)
        result = router.route(problem)

        assert result.success
        assert result.plugin_used == "graph_theory"
        assert "path" in result.final_answer.lower()

    def test_solve_logic_problem(self):
        """End-to-end: Solve a logic problem."""
        problem = FormalizedProblem(
            id="e2e-logic-test",
            domain_tags=["logic"],
            objective="simplify (p & q) | (p & ~q)",
            source_document=SourceDocument(),
        )

        router = Router()
        register_all_plugins(router)
        result = router.route(problem)

        assert result.success
        assert result.plugin_used == "logic"
        assert "p" in result.final_answer.lower()

    def test_all_plugins_work(self):
        """End-to-end: Verify all 8 plugins produce successful results."""
        test_cases = [
            ("calculus", "\\frac{d}{dx} x^3", "calculus"),
            ("linear_algebra", "eigenvalues of [[1,2],[3,4]]", "linear_algebra"),
            ("statistics", "mean of [1,2,3,4,5]", "statistics"),
            ("number_theory", "is 97 prime", "number_theory"),
            ("combinatorics", "combinations of 10 choose 3", "combinatorics"),
            ("graph_theory", "shortest path from A to E", "graph_theory"),
            ("logic", "simplify (p & q) | (p & ~q)", "logic"),
        ]

        router = Router()
        register_all_plugins(router)

        for domain, objective, expected_plugin in test_cases:
            problem = FormalizedProblem(
                id=f"e2e-{domain}",
                domain_tags=[domain],
                objective=objective,
                source_document=SourceDocument(),
            )

            result = router.route(problem)

            assert result.success, f"{domain} failed: {result.failure_reason}"
            assert result.plugin_used == expected_plugin, (
                f"{domain}: expected {expected_plugin}, got {result.plugin_used}"
            )

    def test_state_persistence(self):
        """End-to-end: Problems are saved to database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            state = StateManager(db_path=db_path)

            problem = FormalizedProblem(
                id="persist-test",
                title="Persistence Test",
                domain_tags=["test"],
            )

            state.save_problem(problem)

            problems = state.list_problems()
            assert len(problems) == 1
            assert problems[0]["id"] == "persist-test"

            retrieved = state.get_problem("persist-test")
            assert retrieved is not None
            assert retrieved.title == "Persistence Test"

    def test_math_result_saved(self):
        """End-to-end: Math results are persisted with problems."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            state = StateManager(db_path=db_path)

            problem = FormalizedProblem(
                id="math-persist-test",
                domain_tags=["calculus"],
                objective="\\frac{d}{dx} x^2",
                source_document=SourceDocument(),
            )
            state.save_problem(problem)

            router = Router(state_manager=state)
            register_all_plugins(router)
            result = router.route(problem)

            assert result.success

            problems = state.list_problems(status="solved")
            assert len(problems) == 1
            assert problems[0]["id"] == "math-persist-test"

    def test_linear_algebra_invalid_input_fails_instead_of_using_defaults(self):
        """End-to-end: malformed linear algebra input should fail loudly."""
        problem = FormalizedProblem(
            id="e2e-la-invalid",
            domain_tags=["linear_algebra"],
            objective='{"operation": "matrix_multiply", "A": [[1, 2], [3, 4]]}',
            source_document=SourceDocument(),
        )

        router = Router()
        register_all_plugins(router)
        result = router.route(problem)

        assert result.success is False
        assert "Missing required matrix input" in str(result.failure_reason)

    def test_statistics_invalid_input_fails_instead_of_using_defaults(self):
        """End-to-end: malformed statistics input should fail loudly."""
        problem = FormalizedProblem(
            id="e2e-stats-invalid",
            domain_tags=["statistics"],
            objective='{"operation": "correlation", "x": [1, 2, 3]}',
            source_document=SourceDocument(),
        )

        router = Router()
        register_all_plugins(router)
        result = router.route(problem)

        assert result.success is False
        assert "Missing required statistics input" in str(result.failure_reason)
