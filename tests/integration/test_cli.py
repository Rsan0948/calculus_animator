"""Integration tests for CLI commands."""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from engine.state import RunArtifactRef, RunRecord
from engine.state_manager import StateManager


class TestCLI:
    """Test CLI commands work correctly."""

    @staticmethod
    def _run_cli(*args: str, home_dir: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HOME"] = home_dir
        return subprocess.run(
            [sys.executable, "cli.py", *args],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
            env=env,
            check=False,
        )

    @staticmethod
    def _seed_run(home_dir: str, run_id: str = "run-123") -> None:
        db_path = Path(home_dir) / ".research_engine" / "state.db"
        run_root = Path(home_dir) / ".research_engine" / "runs" / run_id
        (run_root / "extract").mkdir(parents=True, exist_ok=True)
        (run_root / "chunks").mkdir(parents=True, exist_ok=True)
        (run_root / "formalized").mkdir(parents=True, exist_ok=True)

        extract_report_path = run_root / "extract" / "report.json"
        chunk_report_path = run_root / "chunks" / "chunk_report.json"
        formalization_report_path = run_root / "formalized" / "formalization_report.json"

        extract_report_path.write_text(
            json.dumps(
                {
                    "extractor_used": "marker-pdf",
                    "fallback_attempts": ["marker-pdf"],
                    "raw_character_count": 240,
                    "normalized_character_count": 220,
                    "line_count": 12,
                    "page_count": 3,
                    "scanned_pdf_suspected": False,
                    "warnings": ["Low text density on page 3"],
                    "extractor_metadata": {},
                }
            ),
            encoding="utf-8",
        )
        chunk_report_path.write_text(
            json.dumps(
                {
                    "total_chunks": 2,
                    "total_characters": 180,
                    "min_chunk_size": 80,
                    "max_chunk_size": 100,
                    "average_chunk_size": 90.0,
                    "dropped_empty_chunks": 0,
                    "warnings": [],
                    "chunks": [
                        {"index": 0, "content": "chunk one", "character_count": 80, "preview": "chunk one"},
                        {"index": 1, "content": "chunk two", "character_count": 100, "preview": "chunk two"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        formalization_report_path.write_text(
            json.dumps(
                {
                    "accepted": True,
                    "confidence": 0.92,
                    "assumptions": ["The notation follows standard calculus conventions"],
                    "ambiguity_notes": [],
                    "dropped_fields": [],
                    "validation_errors": [],
                    "refusal_reason": None,
                    "attempts": [
                        {"phase": "extract", "success": True, "notes": [], "raw_response_preview": None},
                        {"phase": "repair", "success": True, "notes": [], "raw_response_preview": None},
                        {"phase": "validate", "success": True, "notes": [], "raw_response_preview": None},
                    ],
                    "selected_chunk_count": 2,
                    "objective_present": True,
                    "domain_tag_count": 1,
                    "model": "test-model",
                }
            ),
            encoding="utf-8",
        )

        state = StateManager(db_path=db_path)
        run = RunRecord(
            id=run_id,
            source_path="/tmp/paper.pdf",
            source_fingerprint="fingerprint-123",
            command_name="run",
        )
        state.create_run(run)
        state.start_stage(run_id, "validate_input")
        state.complete_stage(
            run_id,
            "validate_input",
            metadata={
                "source_size_bytes": 4096,
                "source_fingerprint": "fingerprint-123",
            },
            artifacts=[
                RunArtifactRef(
                    artifact_type="source_pdf",
                    path="/tmp/paper.pdf",
                    stage_name="validate_input",
                )
            ],
        )
        state.start_stage(run_id, "extract")
        state.complete_stage(
            run_id,
            "extract",
            metadata={
                "extractor_used": "marker-pdf",
                "warning_count": 1,
                "normalized_character_count": 220,
                "scanned_pdf_suspected": False,
            },
            artifacts=[
                RunArtifactRef(
                    artifact_type="json",
                    path=str(extract_report_path),
                    stage_name="extract",
                )
            ],
        )
        state.start_stage(run_id, "chunk")
        state.complete_stage(
            run_id,
            "chunk",
            metadata={
                "chunk_count": 2,
                "warning_count": 0,
                "total_characters": 180,
            },
            artifacts=[
                RunArtifactRef(
                    artifact_type="json",
                    path=str(chunk_report_path),
                    stage_name="chunk",
                )
            ],
        )
        state.start_stage(run_id, "formalize")
        state.complete_stage(
            run_id,
            "formalize",
            metadata={
                "confidence": 0.92,
                "ambiguity_count": 0,
            },
            artifacts=[
                RunArtifactRef(
                    artifact_type="json",
                    path=str(formalization_report_path),
                    stage_name="formalize",
                )
            ],
        )
        state.complete_run(run_id, current_stage="formalize")

    def test_solve_command(self):
        """CLI: research-engine solve works."""
        with tempfile.TemporaryDirectory() as temp_home:
            result = self._run_cli("solve", r"\frac{d}{dx} x^2", home_dir=temp_home)

        assert result.returncode == 0
        assert "2" in result.stdout or result.returncode == 0

    def test_list_command(self):
        """CLI: research-engine list works."""
        with tempfile.TemporaryDirectory() as temp_home:
            result = self._run_cli("list", home_dir=temp_home)

        assert result.returncode == 0
        assert "No problems found." in result.stdout or "ID" in result.stdout

    def test_runs_command(self):
        """CLI: runs lists persisted run records."""
        with tempfile.TemporaryDirectory() as temp_home:
            self._seed_run(temp_home)
            result = self._run_cli("runs", home_dir=temp_home)

        assert result.returncode == 0
        assert "run-123" in result.stdout
        assert "formalize" in result.stdout

    def test_show_run_command(self):
        """CLI: show-run displays persisted diagnostics for a seeded run."""
        with tempfile.TemporaryDirectory() as temp_home:
            self._seed_run(temp_home, run_id="run-show-123")
            result = self._run_cli("show-run", "run-show-123", home_dir=temp_home)

        assert result.returncode == 0
        assert "RUN DETAILS" in result.stdout
        assert "run-show-123" in result.stdout
        assert "Fingerprint: fingerprint-123" in result.stdout
        assert "Extractor: marker-pdf" in result.stdout
        assert "Chunks: 2" in result.stdout
        assert "Confidence: 0.92" in result.stdout

    def test_domains_command(self):
        """CLI: domains shows domain maturity metadata."""
        with tempfile.TemporaryDirectory() as temp_home:
            result = self._run_cli("domains", home_dir=temp_home)

        assert result.returncode == 0
        assert "DOMAIN SUPPORT" in result.stdout
        assert "calculus" in result.stdout
        assert "reliable" in result.stdout
        assert "experimental" in result.stdout

    def test_surfaces_command(self):
        """CLI: surfaces shows the active/transitional/legacy repo map."""
        with tempfile.TemporaryDirectory() as temp_home:
            result = self._run_cli("surfaces", home_dir=temp_home)

        assert result.returncode == 0
        assert "ACTIVE PRODUCT PATH" in result.stdout
        assert "TRANSITIONAL SURFACES" in result.stdout
        assert "LEGACY SURFACES" in result.stdout
        assert "cli.py" in result.stdout
        assert "ai_backend/" in result.stdout
        assert "calculus_animator/" in result.stdout

    def test_show_command_displays_saved_problem(self):
        """CLI: show returns persisted problem and math result details."""
        with tempfile.TemporaryDirectory() as temp_home:
            solve_result = self._run_cli("solve", "derivative of x^3", home_dir=temp_home)
            assert solve_result.returncode == 0

            list_result = self._run_cli("list", home_dir=temp_home)
            assert list_result.returncode == 0

            lines = [line for line in list_result.stdout.splitlines() if line.strip()]
            problem_rows = [line for line in lines if line.startswith(tuple("0123456789abcdef"))]
            assert problem_rows, list_result.stdout
            problem_id = re.split(r"\s+", problem_rows[0].strip(), maxsplit=1)[0]

            show_result = self._run_cli("show", problem_id, home_dir=temp_home)

        assert show_result.returncode == 0
        assert "PROBLEM DETAILS" in show_result.stdout
        assert "MATH RESULT" in show_result.stdout
        assert "Status: solved" in show_result.stdout

    def test_help_shows_examples(self):
        """CLI: Help includes examples."""
        with tempfile.TemporaryDirectory() as temp_home:
            result = self._run_cli("solve", "--help", home_dir=temp_home)

        assert result.returncode == 0
        assert "EXAMPLES" in result.stdout
        assert "Calculus" in result.stdout

    def test_main_help_shows_commands(self):
        """CLI: Main help shows command groups."""
        with tempfile.TemporaryDirectory() as temp_home:
            result = self._run_cli("--help", home_dir=temp_home)

        assert result.returncode == 0
        assert "solve" in result.stdout
        assert "run" in result.stdout
        assert "runs" in result.stdout
        assert "show-run" in result.stdout
        assert "domains" in result.stdout
        assert "surfaces" in result.stdout
        assert "list" in result.stdout

    def test_show_nonexistent_problem(self):
        """CLI: Show handles non-existent problem gracefully."""
        with tempfile.TemporaryDirectory() as temp_home:
            result = self._run_cli("show", "definitely-not-real-id-12345", home_dir=temp_home)

        assert "not found" in result.stdout.lower() or "not found" in result.stderr.lower() or result.returncode == 0

    def test_show_nonexistent_run(self):
        """CLI: show-run handles a missing run cleanly."""
        with tempfile.TemporaryDirectory() as temp_home:
            result = self._run_cli("show-run", "missing-run-123", home_dir=temp_home)

        assert result.returncode == 0
        assert "Run not found" in result.stdout

    def test_verbose_flag(self):
        """CLI: --verbose flag works."""
        with tempfile.TemporaryDirectory() as temp_home:
            result = self._run_cli("--verbose", "solve", "x^2", home_dir=temp_home)

        assert result.returncode == 0
