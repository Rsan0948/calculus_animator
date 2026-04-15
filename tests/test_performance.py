"""
Performance benchmarks and regression tests.

These tests ensure that core operations remain performant.
Run with: pytest tests/test_performance.py -v --benchmark-only
"""
import pytest
import json
from typing import Dict, Any

from math_engine.router import Router
from math_engine.plugins.calculus.plugin import CalculusPlugin
from math_engine.plugins.linear_algebra.plugin import LinearAlgebraPlugin
from math_engine.plugins.statistics.plugin import StatisticsPlugin
from math_engine.plugins.optimization.plugin import OptimizationPlugin
from math_engine.plugins.number_theory.plugin import NumberTheoryPlugin
from math_engine.plugins.combinatorics.plugin import CombinatoricsPlugin
from math_engine.plugins.graph_theory.plugin import GraphTheoryPlugin
from math_engine.plugins.logic.plugin import LogicPlugin
from engine.state import FormalizedProblem
from math_engine.input_parser import InputParser


# ============== Router Performance ==============


@pytest.fixture
def populated_router():
    """Router with all 8 plugins registered."""
    router = Router()
    router.register(CalculusPlugin())
    router.register(LinearAlgebraPlugin())
    router.register(StatisticsPlugin())
    router.register(OptimizationPlugin())
    router.register(NumberTheoryPlugin())
    router.register(CombinatoricsPlugin())
    router.register(GraphTheoryPlugin())
    router.register(LogicPlugin())
    return router


def test_router_routing_performance(benchmark, populated_router):
    """Benchmark router plugin selection."""
    problem = FormalizedProblem(
        title="Matrix multiplication",
        problem_type="linear_algebra",
        domain_tags=["linear_algebra"],
        objective=json.dumps({
            "operation": "multiply",
            "matrix_a": [[1, 2], [3, 4]],
            "matrix_b": [[5, 6], [7, 8]]
        })
    )
    
    result = benchmark(populated_router.route, problem)
    assert result.success


def test_router_natural_language_parsing_performance(benchmark, populated_router):
    """Benchmark natural language parsing and routing."""
    problem = FormalizedProblem(
        title="Calculate derivative",
        problem_type="calculus",
        domain_tags=["calculus"],
        objective="Find the derivative of x^3 + 2*x with respect to x"
    )
    
    result = benchmark(populated_router.route, problem)
    assert result.success


# ============== Plugin Performance ==============


def test_calculus_derivative_performance(benchmark):
    """Benchmark calculus derivative computation."""
    plugin = CalculusPlugin()
    problem = FormalizedProblem(
        title="Derivative test",
        problem_type="calculus",
        domain_tags=["calculus"],
        objective="\\frac{d}{dx} (x^3 + 2*x^2 - 5*x + 1)"
    )
    
    result = benchmark(plugin.solve, problem)
    assert result.success


def test_linear_algebra_matrix_multiply_performance(benchmark):
    """Benchmark matrix multiplication."""
    plugin = LinearAlgebraPlugin()
    # 50x50 matrix multiplication (smaller for benchmark)
    import numpy as np
    size = 50
    matrix_a = np.random.rand(size, size).tolist()
    matrix_b = np.random.rand(size, size).tolist()
    
    problem = FormalizedProblem(
        title="Matrix multiply",
        problem_type="linear_algebra",
        domain_tags=["linear_algebra"],
        objective=json.dumps({
            "operation": "multiply",
            "matrix_a": matrix_a,
            "matrix_b": matrix_b
        })
    )
    
    result = benchmark(plugin.solve, problem)
    assert result.success


def test_statistics_large_dataset_performance(benchmark):
    """Benchmark statistics on large dataset."""
    plugin = StatisticsPlugin()
    # 10,000 data points
    data = list(range(10000))
    
    problem = FormalizedProblem(
        title="Statistics test",
        problem_type="statistics",
        domain_tags=["statistics"],
        objective=json.dumps({
            "operation": "describe",
            "data": data
        })
    )
    
    result = benchmark(plugin.solve, problem)
    assert result.success


def test_graph_theory_shortest_path_performance(benchmark):
    """Benchmark shortest path problem."""
    plugin = GraphTheoryPlugin()
    # Use natural language input like integration tests
    problem = FormalizedProblem(
        title="Shortest path",
        problem_type="graph_theory",
        domain_tags=["graph_theory"],
        objective="shortest path from A to E"
    )
    
    result = benchmark(plugin.solve, problem)
    assert result.success


# ============== Input Parser Performance ==============


@pytest.fixture
def input_parser():
    return InputParser()


def test_input_parser_matrix_extraction_performance(benchmark, input_parser):
    """Benchmark matrix extraction from text."""
    text = "Multiply [[1,2,3],[4,5,6],[7,8,9]] by [[9,8,7],[6,5,4],[3,2,1]]"
    
    result = benchmark(input_parser.extract_matrix, text)
    assert result is not None


def test_input_parser_domain_parsing_performance(benchmark, input_parser):
    """Benchmark domain-specific parsing."""
    text = "Calculate the mean and standard deviation of [1,2,3,4,5,6,7,8,9,10]"
    
    result = benchmark(input_parser.parse_for_domain, text, "statistics")
    assert result is not None


# ============== End-to-End Performance ==============


def test_e2e_solve_problem_performance(benchmark, populated_router):
    """Benchmark complete solve flow."""
    problem = FormalizedProblem(
        title="Integration test",
        problem_type="calculus",
        domain_tags=["calculus"],
        objective="\\int_0^5 2*x \\, dx"
    )
    
    def solve_flow():
        result = populated_router.route(problem)
        return result.success, result.final_answer
    
    success, answer = benchmark(solve_flow)
    assert success


# ============== Regression Thresholds ==============


@pytest.mark.benchmark(
    group="routing",
    max_time=1.0,  # Should complete in under 1 second
)
def test_router_routing_regression(benchmark, populated_router):
    """Regression test: routing must stay fast."""
    problem = FormalizedProblem(
        title="Quick test",
        problem_type="calculus",
        domain_tags=["calculus"],
        objective="\\frac{d}{dx} x^2"
    )
    
    result = benchmark(populated_router.route, problem)
    # Ensure median time is under threshold
    assert benchmark.stats.stats.median < 0.1  # 100ms threshold


@pytest.mark.benchmark(
    group="parsing",
)
def test_parsing_regression(benchmark, input_parser):
    """Regression test: parsing must stay fast."""
    text = "Find the determinant of [[1,2],[3,4]]"
    
    result = benchmark(input_parser.parse_for_domain, text, "linear_algebra")
    assert benchmark.stats.stats.median < 0.05  # 50ms threshold
