"""Tests for the persisted run graph service."""

from pathlib import Path

import pytest

import engine.run_service as run_service_module
from engine.run_service import RunService
from engine.state import (
    ExtractionReport,
    ExtractionResult,
    FormalizationAttemptReport,
    FormalizationReport,
    FormalizedProblem,
    GeneratedFile,
    GuardrailReport,
    MVPAttempt,
    MVPOutput,
    MathResult,
    SourceDocument,
)
from engine.state_manager import StateManager


class _ExtractorStub:
    def __init__(self) -> None:
        self.calls = 0

    def extract_with_report(self, pdf_path: Path) -> ExtractionResult:
        self.calls += 1
        return ExtractionResult(
            text="# Sample Problem\n\nDifferentiate x^2 with respect to x.",
            report=ExtractionReport(
                extractor_used="stub-extractor",
                fallback_attempts=[],
                raw_character_count=52,
                normalized_character_count=52,
                line_count=3,
            ),
        )


class _ChunkerStub:
    def __init__(self) -> None:
        self.calls = 0

    def chunk(self, markdown_text: str) -> list[str]:
        self.calls += 1
        return ["Differentiate x^2 with respect to x and return the symbolic derivative."]


class _FormalizerStub:
    def __init__(self) -> None:
        self.calls = 0

    def formalize_with_report(
        self,
        chunks: list[str],
        source_doc: SourceDocument,
    ) -> tuple[FormalizedProblem | None, FormalizationReport]:
        self.calls += 1
        problem = FormalizedProblem(
            id="problem-123",
            source_document=source_doc,
            title="Derivative Problem",
            domain_tags=["calculus"],
            objective="derivative of x^2",
            confidence=0.93,
        )
        report = FormalizationReport(
            accepted=True,
            confidence=0.93,
            selected_chunk_count=len(chunks),
            objective_present=True,
            domain_tag_count=1,
            attempts=[
                FormalizationAttemptReport(phase="extract", success=True),
                FormalizationAttemptReport(phase="repair", success=True),
                FormalizationAttemptReport(phase="validate", success=True),
            ],
            model="stub-model",
        )
        return problem, report


class _RouterStub:
    def __init__(self) -> None:
        self.analyze_calls = 0
        self.solve_calls = 0

    def analyze(self, problem: FormalizedProblem) -> dict[str, object]:
        self.analyze_calls += 1
        return {
            "success": True,
            "selected_plugin": "calculus",
            "selected_score": 1.0,
            "scores": [{"plugin": "calculus", "score": 1.0}],
            "normalized_objective": problem.objective,
            "preparsed": False,
            "failure_reason": None,
        }

    def solve_with_analysis(self, problem: FormalizedProblem, analysis: dict[str, object]) -> MathResult:
        self.solve_calls += 1
        return MathResult(
            problem_id=problem.id,
            plugin_used="calculus",
            success=True,
            final_answer="2*x",
        )


class _PassingOrchestratorStub:
    def __init__(self) -> None:
        self.calls = 0

    def generate_mvp(self, math_result: MathResult) -> MVPOutput:
        self.calls += 1
        return MVPOutput(
            problem_id=math_result.problem_id,
            root_directory="/tmp/generated-mvp",
            files=[GeneratedFile(relative_path="main.py", content="print('ok')")],
            attempt_history=[
                MVPAttempt(
                    attempt_number=1,
                    generated_files=["main.py"],
                    overall_pass=True,
                    math_validation_pass=True,
                    violation_count=0,
                    violation_check_ids=[],
                )
            ],
            guardrail_report=GuardrailReport(
                target_path="/tmp/generated-mvp",
                overall_pass=True,
                math_validation_pass=True,
                violations=[],
            ),
        )


class _FlakyOrchestratorStub:
    def __init__(self) -> None:
        self.calls = 0

    def generate_mvp(self, math_result: MathResult) -> MVPOutput:
        self.calls += 1
        passed = self.calls > 1
        return MVPOutput(
            problem_id=math_result.problem_id,
            root_directory="/tmp/generated-mvp",
            files=[GeneratedFile(relative_path="main.py", content="print('ok')")],
            attempt_history=[
                MVPAttempt(
                    attempt_number=self.calls,
                    generated_files=["main.py"],
                    overall_pass=passed,
                    math_validation_pass=passed,
                    violation_count=0 if passed else 1,
                    violation_check_ids=[] if passed else ["type-hints"],
                )
            ],
            guardrail_report=GuardrailReport(
                target_path="/tmp/generated-mvp",
                overall_pass=passed,
                math_validation_pass=passed,
                violations=[],
            ),
        )


@pytest.fixture
def temp_run_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(run_service_module, "validate_pdf", lambda path: None)

    state_manager = StateManager(db_path=tmp_path / "state.db")
    extractor = _ExtractorStub()
    chunker = _ChunkerStub()
    formalizer = _FormalizerStub()
    router = _RouterStub()
    orchestrator = _PassingOrchestratorStub()

    service = RunService(
        state_manager=state_manager,
        runs_root=tmp_path / "runs",
        extractor=extractor,
        chunker=chunker,
        formalizer=formalizer,
        router_factory=lambda: router,
        orchestrator_factory=lambda run_dir: orchestrator,
    )
    return service, extractor, chunker, formalizer, router, orchestrator


def test_run_pdf_records_stage_state_and_artifacts(
    temp_run_service: tuple[RunService, _ExtractorStub, _ChunkerStub, _FormalizerStub, _RouterStub, _PassingOrchestratorStub],
    tmp_path: Path,
) -> None:
    service, extractor, chunker, formalizer, router, orchestrator = temp_run_service
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    run = service.run_pdf(pdf_path)

    assert run.status == "completed"
    assert run.problem_id == "problem-123"
    assert extractor.calls == 1
    assert chunker.calls == 1
    assert formalizer.calls == 1
    assert router.analyze_calls == 1
    assert router.solve_calls == 1
    assert orchestrator.calls == 1

    stages = service.get_run_stages(run.id)
    assert [stage.stage_name for stage in stages] == [
        "validate_input",
        "extract",
        "chunk",
        "formalize",
        "route",
        "solve",
        "generate_mvp",
    ]
    assert all(stage.status == "completed" for stage in stages)

    extract_report_path = tmp_path / "runs" / run.id / "extract" / "report.json"
    chunk_report_path = tmp_path / "runs" / run.id / "chunks" / "chunk_report.json"
    formalization_report_path = tmp_path / "runs" / run.id / "formalized" / "formalization_report.json"
    formalized_path = tmp_path / "runs" / run.id / "formalized" / "problem.json"
    solve_path = tmp_path / "runs" / run.id / "solve" / "math_result.json"
    mvp_path = tmp_path / "runs" / run.id / "mvp" / "summary.json"
    assert extract_report_path.exists()
    assert chunk_report_path.exists()
    assert formalization_report_path.exists()
    assert formalized_path.exists()
    assert solve_path.exists()
    assert mvp_path.exists()


def test_resume_run_restarts_from_failed_stage_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_service_module, "validate_pdf", lambda path: None)

    state_manager = StateManager(db_path=tmp_path / "state.db")
    extractor = _ExtractorStub()
    chunker = _ChunkerStub()
    formalizer = _FormalizerStub()
    router = _RouterStub()
    orchestrator = _FlakyOrchestratorStub()

    service = RunService(
        state_manager=state_manager,
        runs_root=tmp_path / "runs",
        extractor=extractor,
        chunker=chunker,
        formalizer=formalizer,
        router_factory=lambda: router,
        orchestrator_factory=lambda run_dir: orchestrator,
    )

    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    first_run = service.run_pdf(pdf_path)
    assert first_run.status == "failed"
    assert first_run.current_stage == "generate_mvp"

    resumed_run = service.resume_run(first_run.id)
    assert resumed_run.status == "completed"
    assert resumed_run.current_stage == "generate_mvp"

    assert extractor.calls == 1
    assert chunker.calls == 1
    assert formalizer.calls == 1
    assert router.analyze_calls == 1
    assert router.solve_calls == 1
    assert orchestrator.calls == 2


def test_resume_fails_when_source_changes_before_extract_stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_service_module, "validate_pdf", lambda path: None)

    state_manager = StateManager(db_path=tmp_path / "state.db")
    extractor = _ExtractorStub()
    chunker = _ChunkerStub()
    formalizer = _FormalizerStub()
    router = _RouterStub()
    orchestrator = _PassingOrchestratorStub()

    service = RunService(
        state_manager=state_manager,
        runs_root=tmp_path / "runs",
        extractor=extractor,
        chunker=chunker,
        formalizer=formalizer,
        router_factory=lambda: router,
        orchestrator_factory=lambda run_dir: orchestrator,
    )

    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\noriginal\n")

    first_run = service.run_pdf(pdf_path)
    assert first_run.status == "completed"
    assert extractor.calls == 1

    state_manager.invalidate_stage_and_downstream(first_run.id, "extract")
    pdf_path.write_bytes(b"%PDF-1.4\nchanged\n")

    resumed_run = service.resume_run(first_run.id)

    assert resumed_run.status == "failed"
    assert resumed_run.current_stage == "extract"
    assert isinstance(resumed_run.last_error, dict)
    assert resumed_run.last_error["code"] == "stale_source"
    assert extractor.calls == 1
    assert chunker.calls == 1
    assert formalizer.calls == 1
