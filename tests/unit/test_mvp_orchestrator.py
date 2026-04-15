"""Tests for MVP orchestrator persistence-oriented output."""

from datetime import datetime
from pathlib import Path

from engine.state import GuardrailReport, MathResult, Violation
from mvp_generator.orchestrator import Orchestrator


class _ArchitectStub:
    def design(self, math_result: MathResult) -> dict[str, str]:
        return {"main.py": "entrypoint"}


class _AlgorithmStub:
    def implement(self, math_result: MathResult, file_path: str, purpose: str, existing_code=None, violation_feedback=None) -> str:
        return "def solve():\n    return 42\n"


class _TesterStub:
    def write_tests(self, math_result: MathResult, implemented_code: dict[str, str], violation_feedback=None) -> str:
        return "def test_smoke():\n    assert True\n"


class _IntegratorStub:
    def finalize(self, math_result: MathResult, implemented_code: dict[str, str], violation_feedback=None) -> dict[str, str]:
        return {"README.md": "# MVP"}


class _CriticStub:
    def __init__(self) -> None:
        self.calls = 0

    def audit(self, workspace_path: Path, math_result: MathResult | None = None) -> GuardrailReport:
        self.calls += 1
        if self.calls == 1:
            return GuardrailReport(
                target_path=str(workspace_path),
                timestamp=datetime.utcnow(),
                overall_pass=False,
                math_validation_pass=False,
                violations=[Violation(check_id="type-hints", message="Missing hints", severity="medium")],
            )
        return GuardrailReport(
            target_path=str(workspace_path),
            timestamp=datetime.utcnow(),
            overall_pass=True,
            math_validation_pass=True,
            violations=[],
        )

    def get_violations_by_agent(self, report: GuardrailReport) -> dict[str, list[Violation]]:
        return {"algorithm": report.violations}


def test_generate_mvp_records_attempt_history(tmp_path: Path) -> None:
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.workspace_root = tmp_path
    orchestrator.architect = _ArchitectStub()
    orchestrator.algorithm = _AlgorithmStub()
    orchestrator.tester = _TesterStub()
    orchestrator.integrator = _IntegratorStub()
    orchestrator.critic = _CriticStub()

    math_result = MathResult(problem_id="problem-123", plugin_used="calculus", success=True, final_answer="42")

    output = orchestrator.generate_mvp(math_result, max_retries=2)

    assert len(output.attempt_history) == 2
    assert output.attempt_history[0].violation_count == 1
    assert output.attempt_history[0].violation_check_ids == ["type-hints"]
    assert output.attempt_history[1].overall_pass is True
    assert output.guardrail_report is not None
    assert output.guardrail_report.overall_pass is True
