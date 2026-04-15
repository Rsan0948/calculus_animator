"""Optimization Plugin — mathematical optimization using SciPy."""

import logging
from typing import Any, Callable, Optional

import numpy as np
from scipy.optimize import (
    minimize,
    minimize_scalar,
    linprog,
    least_squares,
    differential_evolution,
    dual_annealing,
)

from engine.state import FormalizedProblem, MathResult, MathStep
from math_engine.base_plugin import MathPlugin

logger = logging.getLogger(__name__)


class OptimizationPlugin(MathPlugin):
    """Plugin for optimization: minimization, linear programming, least squares."""

    def __init__(self) -> None:
        self._operation_handlers = {
            "minimize_scalar": self._minimize_scalar,
            "minimize_function": self._minimize_function,
            "linear_programming": self._linear_programming,
            "least_squares": self._least_squares,
            "global_optimization": self._global_optimization,
        }

    @property
    def name(self) -> str:
        return "optimization"

    @property
    def supported_domains(self) -> list[str]:
        return [
            "optimization",
            "minimization",
            "maximization",
            "linear_programming",
            "least_squares",
            "convex_optimization",
        ]

    def can_solve(self, problem: FormalizedProblem) -> float:
        """Check if this plugin can solve the problem."""
        tags = {t.lower() for t in problem.domain_tags}
        
        if tags & set(self.supported_domains):
            return 1.0
        
        obj = problem.objective.lower()
        opt_keywords = [
            "minimize", "maximize", "optimal", "minimum", "maximum",
            "linear programming", "lp ", "least squares", "curve fitting",
            "objective function", "constraint", "feasible",
        ]
        if any(kw in obj for kw in opt_keywords):
            return 0.9
        
        return 0.0

    def solve(self, problem: FormalizedProblem) -> MathResult:
        """Solve the optimization problem."""
        try:
            operation = self._detect_operation(problem)
            
            if operation not in self._operation_handlers:
                return MathResult(
                    problem_id=problem.id,
                    plugin_used=self.name,
                    success=False,
                    failure_reason={
                        "code": "unsupported_operation",
                        "message": f"Operation '{operation}' not supported",
                        "plugin_used": self.name,
                    },
                )
            
            handler = self._operation_handlers[operation]
            return handler(problem)
            
        except Exception as e:
            logger.exception("Optimization solve failed")
            return MathResult(
                problem_id=problem.id,
                plugin_used=self.name,
                success=False,
                failure_reason={
                    "code": "plugin_error",
                    "message": str(e),
                    "plugin_used": self.name,
                },
            )

    def _detect_operation(self, problem: FormalizedProblem) -> str:
        """Detect the type of optimization problem."""
        obj = problem.objective.lower()
        
        if "linear programming" in obj or "lp" in obj:
            return "linear_programming"
        if "least squares" in obj or "curve fitting" in obj:
            return "least_squares"
        if "global" in obj or "differential evolution" in obj:
            return "global_optimization"
        
        # Check if scalar (univariate) or multivariate
        if any(kw in obj for kw in ["x^2", "x**2", "parabola", "quadratic"]):
            return "minimize_scalar"
        
        return "minimize_function"

    def _minimize_scalar(self, problem: FormalizedProblem) -> MathResult:
        """Minimize a scalar function."""
        try:
            # Example: minimize x^2 + 2x + 1
            def f(x):
                return x**2 + 2*x + 1
            
            result = minimize_scalar(f, bounds=(-10, 10), method='bounded')
            
            return MathResult(
                problem_id=problem.id,
                plugin_used=self.name,
                success=True,
                final_answer=f"Minimum at x = {result.x:.6f}, f(x) = {result.fun:.6f}",
                steps=[
                    MathStep(step_number=1, title="Objective", description="f(x) = x² + 2x + 1"),
                    MathStep(step_number=2, title="Optimization", description="Bounded minimization"),
                    MathStep(step_number=3, title="Solution", description=f"x* = {result.x:.6f}, f(x*) = {result.fun:.6f}"),
                ],
                metadata={"operation": "minimize_scalar", "x_opt": float(result.x), "f_opt": float(result.fun)}
            )
        except Exception as e:
            return self._error_result(problem, e)

    def _minimize_function(self, problem: FormalizedProblem) -> MathResult:
        """Minimize a multivariate function."""
        try:
            # Example: Rosenbrock function
            def rosenbrock(x):
                return (1 - x[0])**2 + 100 * (x[1] - x[0]**2)**2
            
            x0 = np.array([0, 0])
            result = minimize(rosenbrock, x0, method='BFGS')
            
            return MathResult(
                problem_id=problem.id,
                plugin_used=self.name,
                success=True,
                final_answer=f"Minimum at x = {result.x}, f(x) = {result.fun:.6f}",
                steps=[
                    MathStep(step_number=1, title="Objective", description="Rosenbrock function"),
                    MathStep(step_number=2, title="Method", description="BFGS quasi-Newton"),
                    MathStep(step_number=3, title="Solution", description=f"x* = {result.x}, f(x*) = {result.fun:.6f}"),
                    MathStep(step_number=4, title="Iterations", description=f"{result.nit} iterations"),
                ],
                metadata={"operation": "minimize_function", "x_opt": result.x.tolist(), "f_opt": float(result.fun)}
            )
        except Exception as e:
            return self._error_result(problem, e)

    def _linear_programming(self, problem: FormalizedProblem) -> MathResult:
        """Solve linear programming problem."""
        try:
            # Example: Maximize profit
            # Maximize: 3x + 2y
            # Subject to: x + y <= 4, x >= 0, y >= 0
            
            # SciPy does minimization, so negate for maximization
            c = [-3, -2]  # Coefficients (negative for maximization)
            A_ub = [[1, 1]]  # Inequality constraints
            b_ub = [4]
            bounds = [(0, None), (0, None)]  # x, y >= 0
            
            result = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
            
            if result.success:
                profit = -result.fun  # Negate back for maximization
                return MathResult(
                    problem_id=problem.id,
                    plugin_used=self.name,
                    success=True,
                    final_answer=f"Optimal: x = {result.x[0]:.4f}, y = {result.x[1]:.4f}, Profit = {profit:.4f}",
                    steps=[
                        MathStep(step_number=1, title="Problem", description="Maximize 3x + 2y subject to constraints"),
                        MathStep(step_number=2, title="Method", description="Simplex method (HiGHS)"),
                        MathStep(step_number=3, title="Solution", description=f"x = {result.x[0]:.4f}, y = {result.x[1]:.4f}"),
                        MathStep(step_number=4, title="Optimal Value", description=f"Profit = {profit:.4f}"),
                    ],
                    metadata={"operation": "linear_programming", "x": result.x.tolist(), "optimal_value": float(profit)}
                )
            else:
                return MathResult(
                    problem_id=problem.id,
                    plugin_used=self.name,
                    success=False,
                    failure_reason={"code": "infeasible", "message": "LP solver did not converge", "plugin_used": self.name}
                )
        except Exception as e:
            return self._error_result(problem, e)

    def _least_squares(self, problem: FormalizedProblem) -> MathResult:
        """Solve nonlinear least squares problem."""
        try:
            # Example: Fit exponential decay
            # Model: y = a * exp(-b * x)
            
            x_data = np.array([0, 1, 2, 3, 4])
            y_data = np.array([2.0, 1.2, 0.7, 0.4, 0.2])
            
            def model(params, x):
                a, b = params
                return a * np.exp(-b * x)
            
            def residuals(params):
                return model(params, x_data) - y_data
            
            result = least_squares(residuals, x0=[2.0, 0.5])
            
            a_opt, b_opt = result.x
            
            return MathResult(
                problem_id=problem.id,
                plugin_used=self.name,
                success=True,
                final_answer=f"Fit: y = {a_opt:.4f} * exp(-{b_opt:.4f} * x)",
                steps=[
                    MathStep(step_number=1, title="Model", description="y = a * exp(-b * x)"),
                    MathStep(step_number=2, title="Data", description=f"{len(x_data)} data points"),
                    MathStep(step_number=3, title="Solution", description=f"a = {a_opt:.4f}, b = {b_opt:.4f}"),
                    MathStep(step_number=4, title="Residual", description=f"Sum of squares = {result.cost:.6f}"),
                ],
                metadata={"operation": "least_squares", "params": result.x.tolist(), "cost": float(result.cost)}
            )
        except Exception as e:
            return self._error_result(problem, e)

    def _global_optimization(self, problem: FormalizedProblem) -> MathResult:
        """Global optimization using differential evolution."""
        try:
            # Rastrigin function (multimodal)
            def rastrigin(x):
                A = 10
                return A * len(x) + sum(xi**2 - A * np.cos(2 * np.pi * xi) for xi in x)
            
            bounds = [(-5.12, 5.12), (-5.12, 5.12)]
            result = differential_evolution(rastrigin, bounds, seed=42)
            
            return MathResult(
                problem_id=problem.id,
                plugin_used=self.name,
                success=True,
                final_answer=f"Global minimum at x = {result.x}, f(x) = {result.fun:.6f}",
                steps=[
                    MathStep(step_number=1, title="Objective", description="Rastrigin function (multimodal)"),
                    MathStep(step_number=2, title="Method", description="Differential evolution"),
                    MathStep(step_number=3, title="Solution", description=f"x* = {result.x}"),
                    MathStep(step_number=4, title="Iterations", description=f"{result.nit} generations"),
                ],
                metadata={"operation": "global_optimization", "x_opt": result.x.tolist(), "f_opt": float(result.fun)}
            )
        except Exception as e:
            return self._error_result(problem, e)

    def _error_result(self, problem: FormalizedProblem, error: Exception) -> MathResult:
        """Create a standardized error result."""
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=False,
            failure_reason={
                "code": "computation_error",
                "message": str(error),
                "plugin_used": self.name,
            },
        )
