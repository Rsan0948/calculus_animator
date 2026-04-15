"""Statistics Plugin — statistical analysis using NumPy and SciPy."""

import json
import logging
from typing import Any

import numpy as np
from scipy import stats

from engine.state import FormalizedProblem, MathResult, MathStep
from math_engine.base_plugin import MathPlugin
from math_engine.input_parser import InputParser

logger = logging.getLogger(__name__)


class StatisticsPlugin(MathPlugin):
    """Plugin for statistics: descriptive stats, distributions, hypothesis tests."""

    @property
    def name(self) -> str:
        return "statistics"

    @property
    def supported_domains(self) -> list[str]:
        return [
            "statistics",
            "probability",
            "hypothesis_testing",
            "descriptive_statistics",
            "distributions",
        ]

    def can_solve(self, problem: FormalizedProblem) -> float:
        tags = {tag.lower() for tag in problem.domain_tags}
        if tags & set(self.supported_domains):
            return 1.0
        objective = problem.objective.lower()
        keywords = [
            "mean",
            "std",
            "variance",
            "correlation",
            "regression",
            "t-test",
            "normal",
            "distribution",
        ]
        return 0.9 if any(keyword in objective for keyword in keywords) else 0.0

    def solve(self, problem: FormalizedProblem) -> MathResult:
        try:
            payload = self._parse_payload(problem.objective)
            operation = self._detect_operation(problem.objective.lower(), payload)
            return getattr(self, f"_{operation}")(problem, payload)
        except Exception as exc:
            logger.exception("Statistics solve failed")
            return self._error_result(problem, exc)

    def _detect_operation(self, objective: str, payload: dict[str, Any]) -> str:
        operation_aliases = {
            "summary": "summary_stats",
            "describe": "summary_stats",
            "summary_stats": "summary_stats",
            "confidence_interval": "confidence_interval",
            "correlation": "correlation",
            "linear_regression": "linear_regression",
            "regression": "linear_regression",
            "t_test": "t_test",
            "t-test": "t_test",
            "normality_test": "normality_test",
            "pdf": "pdf",
            "cdf": "cdf",
        }
        structured_operation = payload.get("operation")
        if isinstance(structured_operation, str):
            normalized = operation_aliases.get(structured_operation.lower())
            if normalized:
                return normalized

        if "summary" in objective or "describe" in objective or "mean" in objective:
            return "summary_stats"
        if "confidence" in objective:
            return "confidence_interval"
        if "correlation" in objective or "pearson" in objective:
            return "correlation"
        if "regression" in objective or "linear fit" in objective:
            return "linear_regression"
        if "t-test" in objective or "ttest" in objective:
            return "t_test"
        if "normal" in objective and "test" in objective:
            return "normality_test"
        if "pdf" in objective or "probability density" in objective:
            return "pdf"
        if "cdf" in objective or "cumulative" in objective:
            return "cdf"

        raise ValueError("Could not determine statistics operation from input")

    def _parse_payload(self, objective: str) -> dict[str, Any]:
        stripped = objective.strip()
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            if stripped.startswith(("{", "[")):
                raise ValueError("Statistics input JSON is malformed") from exc
            payload = InputParser().parse_for_domain(objective, self.name)

        if isinstance(payload, list):
            return {"data": payload}
        if isinstance(payload, dict):
            return payload

        raise ValueError("Statistics input must decode to an object or numeric list")

    def _require_array(self, payload: dict[str, Any], *keys: str) -> np.ndarray:
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            array = np.array(value, dtype=float)
            if array.size == 0:
                raise ValueError(f"{key} must not be empty")
            return array
        joined_keys = ", ".join(keys)
        raise ValueError(f"Missing required statistics input: {joined_keys}")

    def _summary_stats(self, problem: FormalizedProblem, payload: dict[str, Any]) -> MathResult:
        data = self._require_array(payload, "data")
        mean = np.mean(data)
        median = np.median(data)
        std = np.std(data, ddof=1) if len(data) > 1 else 0.0
        q25, q75 = np.percentile(data, [25, 75])
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer=f"Mean: {mean:.4f}, Median: {median:.4f}, Std: {std:.4f}",
            steps=[
                MathStep(
                    step_number=1,
                    title="Summary Statistics",
                    description=f"n={len(data)}, mean={mean:.4f}, std={std:.4f}",
                )
            ],
            metadata={
                "operation": "summary_stats",
                "mean": float(mean),
                "std": float(std),
                "median": float(median),
                "q25": float(q25),
                "q75": float(q75),
            },
        )

    def _confidence_interval(self, problem: FormalizedProblem, payload: dict[str, Any]) -> MathResult:
        data = self._require_array(payload, "data")
        if len(data) < 2:
            raise ValueError("Confidence interval requires at least two data points")
        mean = np.mean(data)
        sem = stats.sem(data)
        interval = stats.t.interval(0.95, len(data) - 1, loc=mean, scale=sem)
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer=f"95% CI: [{interval[0]:.4f}, {interval[1]:.4f}]",
            steps=[
                MathStep(
                    step_number=1,
                    title="Confidence Interval",
                    description=f"95% CI: [{interval[0]:.4f}, {interval[1]:.4f}]",
                )
            ],
            metadata={
                "operation": "confidence_interval",
                "ci_lower": float(interval[0]),
                "ci_upper": float(interval[1]),
            },
        )

    def _correlation(self, problem: FormalizedProblem, payload: dict[str, Any]) -> MathResult:
        x_values = self._require_array(payload, "x")
        y_values = self._require_array(payload, "y")
        if len(x_values) != len(y_values):
            raise ValueError("Correlation requires x and y to have the same length")
        correlation, pvalue = stats.pearsonr(x_values, y_values)
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer=f"Pearson r = {correlation:.4f} (p = {pvalue:.4f})",
            steps=[
                MathStep(
                    step_number=1,
                    title="Correlation",
                    description=f"r = {correlation:.4f}, p = {pvalue:.4f}",
                )
            ],
            metadata={"operation": "correlation", "r": float(correlation), "pvalue": float(pvalue)},
        )

    def _linear_regression(self, problem: FormalizedProblem, payload: dict[str, Any]) -> MathResult:
        x_values = self._require_array(payload, "x")
        y_values = self._require_array(payload, "y")
        if len(x_values) != len(y_values):
            raise ValueError("Linear regression requires x and y to have the same length")
        slope, intercept, r_value, pvalue, _ = stats.linregress(x_values, y_values)
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer=f"y = {slope:.4f}x + {intercept:.4f} (R² = {r_value ** 2:.4f})",
            steps=[
                MathStep(
                    step_number=1,
                    title="Linear Regression",
                    description=f"y = {slope:.4f}x + {intercept:.4f}",
                )
            ],
            metadata={
                "operation": "linear_regression",
                "slope": float(slope),
                "intercept": float(intercept),
                "r2": float(r_value ** 2),
                "pvalue": float(pvalue),
            },
        )

    def _t_test(self, problem: FormalizedProblem, payload: dict[str, Any]) -> MathResult:
        sample_a = self._require_array(payload, "a")
        sample_b = self._require_array(payload, "b")
        t_statistic, pvalue = stats.ttest_ind(sample_a, sample_b)
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer=f"t = {t_statistic:.4f}, p = {pvalue:.4f}",
            steps=[
                MathStep(
                    step_number=1,
                    title="T-Test",
                    description=f"t = {t_statistic:.4f}, p = {pvalue:.4f}",
                )
            ],
            metadata={"operation": "t_test", "t_statistic": float(t_statistic), "pvalue": float(pvalue)},
        )

    def _normality_test(self, problem: FormalizedProblem, payload: dict[str, Any]) -> MathResult:
        data = self._require_array(payload, "data")
        if len(data) < 3:
            raise ValueError("Normality test requires at least three data points")
        statistic, pvalue = stats.shapiro(data)
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer=f"Shapiro-Wilk W = {statistic:.4f}, p = {pvalue:.4f}",
            steps=[
                MathStep(
                    step_number=1,
                    title="Normality Test",
                    description=f"W = {statistic:.4f}, p = {pvalue:.4f}",
                )
            ],
            metadata={"operation": "normality_test", "statistic": float(statistic), "pvalue": float(pvalue)},
        )

    def _pdf(self, problem: FormalizedProblem, payload: dict[str, Any]) -> MathResult:
        distribution = str(payload.get("distribution") or "").lower()
        if not distribution:
            raise ValueError("PDF input must declare a distribution")
        x_raw = payload.get("x")
        if x_raw is None:
            raise ValueError("PDF input must include x")
        x_value = float(x_raw)

        if distribution == "normal":
            result = stats.norm.pdf(x_value)
        elif distribution == "t":
            df_raw = payload.get("df")
            if df_raw is None:
                raise ValueError("t-distribution PDF requires df")
            result = stats.t.pdf(x_value, int(df_raw))
        else:
            raise ValueError(f"Unsupported PDF distribution: {distribution}")

        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer=f"PDF({distribution}, x={x_value}) = {result:.6f}",
            steps=[
                MathStep(
                    step_number=1,
                    title="PDF",
                    description=f"PDF({distribution}, {x_value}) = {result:.6f}",
                )
            ],
            metadata={"operation": "pdf", "distribution": distribution, "x": x_value, "result": float(result)},
        )

    def _cdf(self, problem: FormalizedProblem, payload: dict[str, Any]) -> MathResult:
        distribution = str(payload.get("distribution") or "").lower()
        if not distribution:
            raise ValueError("CDF input must declare a distribution")
        x_raw = payload.get("x")
        if x_raw is None:
            raise ValueError("CDF input must include x")
        x_value = float(x_raw)

        if distribution == "normal":
            result = stats.norm.cdf(x_value)
        else:
            raise ValueError(f"Unsupported CDF distribution: {distribution}")

        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer=f"CDF({distribution}, x={x_value}) = {result:.6f}",
            steps=[
                MathStep(
                    step_number=1,
                    title="CDF",
                    description=f"CDF({distribution}, {x_value}) = {result:.6f}",
                )
            ],
            metadata={"operation": "cdf", "distribution": distribution, "x": x_value, "result": float(result)},
        )

    def _error_result(self, problem: FormalizedProblem, error: Exception) -> MathResult:
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
