"""Tests for StateManager persistence."""

import shutil
import tempfile
from pathlib import Path

from engine.state import (
    FormalizedProblem,
    GeneratedFile,
    GuardrailReport,
    MVPAttempt,
    MVPOutput,
    MathResult,
    MathStep,
    RunArtifactRef,
    RunRecord,
    SourceDocument,
    Violation,
)
from engine.state_manager import StateManager


class TestStateManager:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.state = StateManager(db_path=self.db_path)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)

    def test_save_and_get_problem(self):
        """Test saving and retrieving a problem."""
        problem = FormalizedProblem(
            id="test-123",
            title="Test Problem",
            domain_tags=["calculus"],
            objective="derivative of x^2",
            source_document=SourceDocument(format="pdf", title="test.pdf"),
        )

        self.state.save_problem(problem)
        retrieved = self.state.get_problem("test-123")

        assert retrieved is not None
        assert retrieved.title == "Test Problem"
        assert retrieved.domain_tags == ["calculus"]
        assert retrieved.objective == "derivative of x^2"

    def test_get_problem_not_found(self):
        """Test retrieving a non-existent problem."""
        retrieved = self.state.get_problem("non-existent")
        assert retrieved is None

    def test_list_problems(self):
        """Test listing all problems."""
        problem1 = FormalizedProblem(id="p1", title="Problem 1", domain_tags=["a"])
        problem2 = FormalizedProblem(id="p2", title="Problem 2", domain_tags=["b"])

        self.state.save_problem(problem1)
        self.state.save_problem(problem2)

        problems = self.state.list_problems()
        assert len(problems) == 2
        ids = [problem["id"] for problem in problems]
        assert "p1" in ids
        assert "p2" in ids

    def test_list_problems_by_status(self):
        """Test listing problems filtered by status."""
        problem1 = FormalizedProblem(id="p1", title="Problem 1", domain_tags=["a"])
        problem2 = FormalizedProblem(id="p2", title="Problem 2", domain_tags=["b"])

        self.state.save_problem(problem1)
        self.state.save_problem(problem2)
        self.state.update_problem_status("p1", "solved")

        solved = self.state.list_problems(status="solved")
        pending = self.state.list_problems(status="pending")

        assert len(solved) == 1
        assert solved[0]["id"] == "p1"
        assert len(pending) == 1
        assert pending[0]["id"] == "p2"

    def test_update_problem_status(self):
        """Test updating problem status."""
        problem = FormalizedProblem(id="status-test", title="Status Test")
        self.state.save_problem(problem)

        self.state.update_problem_status("status-test", "solving")

        problems = self.state.list_problems(status="solving")
        assert len(problems) == 1
        assert problems[0]["status"] == "solving"

    def test_delete_problem(self):
        """Test deleting a problem."""
        problem = FormalizedProblem(id="to-delete", title="Delete Me")
        self.state.save_problem(problem)

        self.state.delete_problem("to-delete")

        retrieved = self.state.get_problem("to-delete")
        assert retrieved is None

    def test_save_math_result(self):
        """Test saving a math result."""
        problem = FormalizedProblem(id="math-test", title="Math Test")
        self.state.save_problem(problem)

        result = MathResult(
            problem_id="math-test",
            plugin_used="calculus",
            success=True,
            final_answer="2*x",
            steps=[MathStep(step_number=1, title="Step 1", description="Differentiate")],
        )

        self.state.save_math_result("math-test", result)

        problems = self.state.list_problems(status="solved")
        assert len(problems) == 1
        assert problems[0]["id"] == "math-test"

    def test_save_math_result_failure(self):
        """Test saving a failed math result."""
        problem = FormalizedProblem(id="fail-test", title="Fail Test")
        self.state.save_problem(problem)

        result = MathResult(
            problem_id="fail-test",
            plugin_used="calculus",
            success=False,
            failure_reason={"code": "error", "message": "Test error"},
        )

        self.state.save_math_result("fail-test", result)

        problems = self.state.list_problems(status="failed")
        assert len(problems) == 1
        assert problems[0]["id"] == "fail-test"

    def test_problem_with_variables_and_constraints(self):
        """Test saving a problem with variables and constraints."""
        from engine.state import Constraint, Variable

        problem = FormalizedProblem(
            id="complex-problem",
            title="Complex Problem",
            domain_tags=["optimization"],
            objective="minimize f(x)",
            variables=[
                Variable(symbol="x", description="decision variable", domain="ℝ"),
                Variable(symbol="y", description="auxiliary", domain="ℝ+"),
            ],
            constraints=[
                Constraint(kind="inequality", expression_latex="x \\geq 0", description="non-negative")
            ],
            source_document=SourceDocument(format="pdf", title="paper.pdf"),
        )

        self.state.save_problem(problem)
        retrieved = self.state.get_problem("complex-problem")

        assert retrieved is not None
        assert len(retrieved.variables) == 2
        assert retrieved.variables[0].symbol == "x"
        assert len(retrieved.constraints) == 1

    def test_save_and_get_mvp_preserves_report_and_attempts(self):
        """Test saving an MVP preserves full report metadata and attempt history."""
        report = GuardrailReport(
            target_path="/tmp/workspace",
            overall_pass=False,
            math_validation_pass=False,
            violations=[
                Violation(
                    check_id="type-hints",
                    file_path="main.py",
                    line_number=4,
                    message="Missing type hints",
                    severity="medium",
                )
            ],
            audit_summary={"critic": "failed"},
        )
        problem = FormalizedProblem(id="mvp-test", title="MVP Test")
        self.state.save_problem(problem)

        mvp = MVPOutput(
            problem_id="mvp-test",
            root_directory="/tmp/workspace",
            files=[GeneratedFile(relative_path="main.py", content="print('x')", purpose="entrypoint")],
            guardrail_report=report,
            attempt_history=[
                MVPAttempt(
                    attempt_number=1,
                    generated_files=["main.py"],
                    overall_pass=False,
                    math_validation_pass=False,
                    violation_count=1,
                    violation_check_ids=["type-hints"],
                )
            ],
            install_command="pip install -e .[dev]",
            run_command="python main.py",
        )

        self.state.save_mvp("mvp-test", "mvp-test_math", mvp)
        retrieved = self.state.get_mvp("mvp-test")

        assert retrieved is not None
        assert retrieved.guardrail_report is not None
        assert retrieved.guardrail_report.audit_summary == {"critic": "failed"}
        assert len(retrieved.guardrail_report.violations) == 1
        assert retrieved.guardrail_report.violations[0].check_id == "type-hints"
        assert len(retrieved.attempt_history) == 1
        assert retrieved.attempt_history[0].violation_check_ids == ["type-hints"]
        assert retrieved.files[0].purpose == "entrypoint"
        assert retrieved.install_command == "pip install -e .[dev]"
        assert retrieved.run_command == "python main.py"

    def test_run_lifecycle_round_trips_stages_and_artifacts(self):
        """Test run metadata, stage state, and artifact refs round-trip from SQLite."""
        run = RunRecord(
            id="run-123",
            source_path="/tmp/input.pdf",
            source_fingerprint="fingerprint-123",
            command_name="run",
        )
        self.state.create_run(run)

        artifact = RunArtifactRef(
            artifact_type="json",
            path="/tmp/run-123/chunks.json",
            stage_name="chunk",
            summary="Chunk manifest",
            metadata={"chunk_count": 2},
            content_hash="abc123",
        )

        self.state.start_stage("run-123", "chunk", metadata={"phase": "starting"})
        self.state.complete_stage(
            "run-123",
            "chunk",
            metadata={"chunk_count": 2},
            artifacts=[artifact],
        )
        self.state.complete_run("run-123", current_stage="chunk")

        retrieved_run = self.state.get_run("run-123")
        assert retrieved_run is not None
        assert retrieved_run.status == "completed"
        assert retrieved_run.current_stage == "chunk"

        stages = self.state.get_run_stages("run-123")
        assert len(stages) == 1
        assert stages[0].stage_name == "chunk"
        assert stages[0].status == "completed"
        assert len(stages[0].artifacts) == 1
        assert stages[0].artifacts[0].metadata == {"chunk_count": 2}

    def test_invalidate_stage_and_downstream_marks_rows_and_clears_artifacts(self):
        """Test invalidation clears downstream artifact refs and marks stages invalidated."""
        run = RunRecord(
            id="run-456",
            source_path="/tmp/input.pdf",
            source_fingerprint="fingerprint-456",
            command_name="run",
        )
        self.state.create_run(run)

        route_artifact = RunArtifactRef(
            artifact_type="json",
            path="/tmp/run-456/route.json",
            stage_name="route",
        )
        solve_artifact = RunArtifactRef(
            artifact_type="json",
            path="/tmp/run-456/math_result.json",
            stage_name="solve",
        )

        self.state.complete_stage("run-456", "route", artifacts=[route_artifact])
        self.state.complete_stage("run-456", "solve", artifacts=[solve_artifact])
        self.state.invalidate_stage_and_downstream("run-456", "route")

        stages = {stage.stage_name: stage for stage in self.state.get_run_stages("run-456")}
        assert stages["route"].status == "invalidated"
        assert stages["solve"].status == "invalidated"
        assert self.state.get_run_artifacts("run-456", "route") == []
        assert self.state.get_run_artifacts("run-456", "solve") == []
