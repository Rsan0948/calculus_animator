"""Linear Algebra Plugin — matrix operations using NumPy and SciPy."""

import json
import logging
from typing import Any

import numpy as np
from scipy import linalg

from engine.state import FormalizedProblem, MathResult, MathStep
from math_engine.base_plugin import MathPlugin
from math_engine.input_parser import InputParser

logger = logging.getLogger(__name__)


class LinearAlgebraPlugin(MathPlugin):
    """Plugin for linear algebra: matrices, vectors, systems, decompositions."""

    @property
    def name(self) -> str:
        return "linear_algebra"

    @property
    def supported_domains(self) -> list[str]:
        return [
            "linear_algebra",
            "matrix",
            "vector",
            "linear_system",
            "eigenvalue",
            "matrix_decomposition",
        ]

    def can_solve(self, problem: FormalizedProblem) -> float:
        tags = {tag.lower() for tag in problem.domain_tags}
        if tags & set(self.supported_domains):
            return 1.0
        objective = problem.objective.lower()
        keywords = ["matrix", "eigenvalue", "determinant", "inverse", "linear system", "solve"]
        return 0.9 if any(keyword in objective for keyword in keywords) else 0.0

    def solve(self, problem: FormalizedProblem) -> MathResult:
        try:
            payload = self._parse_payload(problem.objective)
            operation = self._detect_operation(problem.objective.lower(), payload)
            return getattr(self, f"_{operation}")(problem, payload)
        except Exception as exc:
            logger.exception("Linear algebra solve failed")
            return self._error_result(problem, exc)

    def _detect_operation(self, objective: str, payload: dict[str, Any]) -> str:
        operation_aliases = {
            "multiply": "matrix_multiply",
            "matrix_multiply": "matrix_multiply",
            "matrix_inverse": "matrix_inverse",
            "inverse": "matrix_inverse",
            "matrix_transpose": "matrix_transpose",
            "transpose": "matrix_transpose",
            "matrix_determinant": "matrix_determinant",
            "determinant": "matrix_determinant",
            "matrix_rank": "matrix_rank",
            "rank": "matrix_rank",
            "eigenvalues": "eigenvalues",
            "eigenvalue": "eigenvalues",
            "solve_linear_system": "solve_linear_system",
            "solve": "solve_linear_system",
            "lu_decomposition": "lu_decomposition",
            "qr_decomposition": "qr_decomposition",
            "svd_decomposition": "svd_decomposition",
            "cholesky_decomposition": "cholesky_decomposition",
        }
        structured_operation = payload.get("operation")
        if isinstance(structured_operation, str):
            normalized = operation_aliases.get(structured_operation.lower())
            if normalized:
                return normalized

        if "multiply" in objective or "product" in objective:
            return "matrix_multiply"
        if "inverse" in objective:
            return "matrix_inverse"
        if "transpose" in objective:
            return "matrix_transpose"
        if "determinant" in objective or "det" in objective:
            return "matrix_determinant"
        if "rank" in objective:
            return "matrix_rank"
        if "eigenvalue" in objective or "eigen" in objective:
            return "eigenvalues"
        if "lu" in objective:
            return "lu_decomposition"
        if "qr" in objective:
            return "qr_decomposition"
        if "svd" in objective or "singular" in objective:
            return "svd_decomposition"
        if "cholesky" in objective:
            return "cholesky_decomposition"
        if "solve" in objective or "system" in objective:
            return "solve_linear_system"

        raise ValueError("Could not determine linear algebra operation from input")

    def _parse_payload(self, objective: str) -> dict[str, Any]:
        stripped = objective.strip()
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            if stripped.startswith(("{", "[")):
                raise ValueError("Linear algebra input JSON is malformed") from exc
            payload = InputParser().parse_for_domain(objective, self.name)

        if isinstance(payload, list):
            return {"A": payload}
        if isinstance(payload, dict):
            return payload

        raise ValueError("Linear algebra input must decode to an object or matrix list")

    def _require_matrix(self, payload: dict[str, Any], *keys: str) -> np.ndarray:
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            matrix = np.array(value, dtype=float)
            if matrix.ndim != 2:
                raise ValueError(f"{key} must be a 2D matrix")
            return matrix
        joined_keys = ", ".join(keys)
        raise ValueError(f"Missing required matrix input: {joined_keys}")

    def _require_vector(self, payload: dict[str, Any], *keys: str) -> np.ndarray:
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            vector = np.array(value, dtype=float)
            if vector.ndim != 1:
                raise ValueError(f"{key} must be a 1D vector")
            return vector
        joined_keys = ", ".join(keys)
        raise ValueError(f"Missing required vector input: {joined_keys}")

    def _matrix_multiply(self, problem: FormalizedProblem, payload: dict[str, Any]) -> MathResult:
        matrix_a = self._require_matrix(payload, "A", "matrix_a")
        matrix_b = self._require_matrix(payload, "B", "matrix_b")
        result = matrix_a @ matrix_b
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer=f"Result:\n{result}",
            steps=[
                MathStep(
                    step_number=1,
                    title="Matrix Multiplication",
                    description=f"A @ B = \n{result}",
                )
            ],
            metadata={"operation": "matrix_multiply", "result": result.tolist()},
        )

    def _matrix_inverse(self, problem: FormalizedProblem, payload: dict[str, Any]) -> MathResult:
        matrix_a = self._require_matrix(payload, "A", "matrix")
        result = np.linalg.inv(matrix_a)
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer=f"A⁻¹ = \n{result}",
            steps=[
                MathStep(
                    step_number=1,
                    title="Matrix Inverse",
                    description=f"A⁻¹ = \n{result}",
                )
            ],
            metadata={"operation": "matrix_inverse", "result": result.tolist()},
        )

    def _matrix_transpose(self, problem: FormalizedProblem, payload: dict[str, Any]) -> MathResult:
        matrix_a = self._require_matrix(payload, "A", "matrix")
        result = matrix_a.T
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer=f"Aᵀ = \n{result}",
            steps=[
                MathStep(
                    step_number=1,
                    title="Matrix Transpose",
                    description=f"Aᵀ = \n{result}",
                )
            ],
            metadata={"operation": "matrix_transpose", "result": result.tolist()},
        )

    def _matrix_determinant(self, problem: FormalizedProblem, payload: dict[str, Any]) -> MathResult:
        matrix_a = self._require_matrix(payload, "A", "matrix")
        result = np.linalg.det(matrix_a)
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer=f"det(A) = {result:.4f}",
            steps=[
                MathStep(
                    step_number=1,
                    title="Determinant",
                    description=f"det(A) = {result:.4f}",
                )
            ],
            metadata={"operation": "matrix_determinant", "result": float(result)},
        )

    def _matrix_rank(self, problem: FormalizedProblem, payload: dict[str, Any]) -> MathResult:
        matrix_a = self._require_matrix(payload, "A", "matrix")
        result = np.linalg.matrix_rank(matrix_a)
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer=f"rank(A) = {result}",
            steps=[
                MathStep(
                    step_number=1,
                    title="Matrix Rank",
                    description=f"rank(A) = {result}",
                )
            ],
            metadata={"operation": "matrix_rank", "result": int(result)},
        )

    def _eigenvalues(self, problem: FormalizedProblem, payload: dict[str, Any]) -> MathResult:
        matrix_a = self._require_matrix(payload, "A", "matrix")
        eigenvalues, _ = np.linalg.eig(matrix_a)
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer=f"Eigenvalues: {eigenvalues}",
            steps=[
                MathStep(
                    step_number=1,
                    title="Eigenvalues",
                    description=f"λ = {eigenvalues}",
                )
            ],
            metadata={"operation": "eigenvalues", "eigenvalues": eigenvalues.tolist()},
        )

    def _solve_linear_system(self, problem: FormalizedProblem, payload: dict[str, Any]) -> MathResult:
        matrix_a = self._require_matrix(payload, "A", "matrix_a")
        vector_b = self._require_vector(payload, "b", "vector_b")
        solution = np.linalg.solve(matrix_a, vector_b)
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer=f"x = {solution}",
            steps=[
                MathStep(
                    step_number=1,
                    title="Solve Ax=b",
                    description=f"x = {solution}",
                )
            ],
            metadata={"operation": "solve_linear_system", "solution": solution.tolist()},
        )

    def _lu_decomposition(self, problem: FormalizedProblem, payload: dict[str, Any]) -> MathResult:
        matrix_a = self._require_matrix(payload, "A", "matrix")
        _, lower, upper = linalg.lu(matrix_a)
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer="A = PLU decomposition computed",
            steps=[
                MathStep(
                    step_number=1,
                    title="LU Decomposition",
                    description="P, L, U matrices computed",
                )
            ],
            metadata={
                "operation": "lu_decomposition",
                "L": lower.tolist(),
                "U": upper.tolist(),
            },
        )

    def _qr_decomposition(self, problem: FormalizedProblem, payload: dict[str, Any]) -> MathResult:
        matrix_a = self._require_matrix(payload, "A", "matrix")
        orthogonal, upper = np.linalg.qr(matrix_a)
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer="A = QR decomposition computed",
            steps=[
                MathStep(
                    step_number=1,
                    title="QR Decomposition",
                    description="Q, R matrices computed",
                )
            ],
            metadata={
                "operation": "qr_decomposition",
                "Q": orthogonal.tolist(),
                "R": upper.tolist(),
            },
        )

    def _svd_decomposition(self, problem: FormalizedProblem, payload: dict[str, Any]) -> MathResult:
        matrix_a = self._require_matrix(payload, "A", "matrix")
        _, singular_values, _ = np.linalg.svd(matrix_a)
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer="A = UΣV* SVD computed",
            steps=[
                MathStep(
                    step_number=1,
                    title="SVD",
                    description=f"Singular values: {singular_values}",
                )
            ],
            metadata={"operation": "svd_decomposition", "singular_values": singular_values.tolist()},
        )

    def _cholesky_decomposition(self, problem: FormalizedProblem, payload: dict[str, Any]) -> MathResult:
        matrix_a = self._require_matrix(payload, "A", "matrix")
        lower = np.linalg.cholesky(matrix_a)
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer="A = LL* Cholesky computed",
            steps=[
                MathStep(
                    step_number=1,
                    title="Cholesky",
                    description="L matrix computed",
                )
            ],
            metadata={"operation": "cholesky_decomposition", "L": lower.tolist()},
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
