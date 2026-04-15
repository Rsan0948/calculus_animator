"""Run graph orchestration for the active research-engine CLI workflow."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Callable, Optional

from engine.state import (
    ChunkReport,
    FormalizationReport,
    FormalizedProblem,
    MVPOutput,
    MathResult,
    RUN_STAGE_ORDER,
    RunArtifactRef,
    RunRecord,
    RunStageName,
    SourceDocument,
)
from engine.state_manager import StateManager
from ingestion.chunking.header_chunker import HeaderChunker
from ingestion.extractors.pdf_extractor import PDFExtractor
from ingestion.formalization.formalizer import Formalizer
from ingestion.validators import build_chunk_report, validate_chunk_report, validate_pdf
from math_engine.plugin_registry import register_all_plugins
from math_engine.router import Router
from mvp_generator.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

DEFAULT_RUNS_ROOT = Path.home() / ".research_engine" / "runs"


class RunServiceError(Exception):
    """Raised when a run cannot be executed or resumed."""


class RunService:
    """Executes and resumes the active product-path run graph."""

    def __init__(
        self,
        state_manager: Optional[StateManager] = None,
        runs_root: Optional[Path] = None,
        extractor: Optional[PDFExtractor] = None,
        chunker: Optional[HeaderChunker] = None,
        formalizer: Optional[Formalizer] = None,
        router_factory: Optional[Callable[[], Router]] = None,
        orchestrator_factory: Optional[Callable[[Path], Orchestrator]] = None,
    ) -> None:
        self.state_manager = state_manager or StateManager()
        self.runs_root = runs_root or DEFAULT_RUNS_ROOT
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self.extractor = extractor or PDFExtractor(output_dir=self.runs_root / "extractor_cache")
        self.chunker = chunker or HeaderChunker()
        self.formalizer = formalizer or Formalizer()
        self._router_factory = router_factory or self._build_router
        self._orchestrator_factory = orchestrator_factory or self._build_orchestrator

    def run_pdf(self, pdf_path: Path, command_name: str = "run") -> RunRecord:
        """Create and execute a fresh run for one PDF."""
        source_path = pdf_path.expanduser().resolve()
        if not source_path.exists() or not source_path.is_file():
            raise RunServiceError(f"PDF not found: {pdf_path}")

        run = RunRecord(
            source_path=str(source_path),
            source_fingerprint=self._fingerprint_file(source_path),
            command_name=command_name,
            config={"original_source_path": str(source_path)},
        )
        self.state_manager.create_run(run)
        return self._execute_run(run.id, "validate_input")

    def resume_run(self, run_id: str) -> RunRecord:
        """Resume the first failed or incomplete stage for an existing run."""
        run = self._require_run(run_id)
        if run.status == "completed":
            return run

        stage_name = self._next_stage_to_run(run_id)
        if stage_name is None:
            return run
        return self._execute_run(run_id, stage_name)

    def retry_stage(self, run_id: str, stage_name: RunStageName) -> RunRecord:
        """Invalidate one stage and rerun from that point forward."""
        self._require_run(run_id)
        self.state_manager.invalidate_stage_and_downstream(run_id, stage_name)
        return self._execute_run(run_id, stage_name)

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        return self.state_manager.get_run(run_id)

    def list_runs(self) -> list[RunRecord]:
        return self.state_manager.list_runs()

    def get_run_stages(self, run_id: str):
        return self.state_manager.get_run_stages(run_id)

    def _execute_run(self, run_id: str, start_stage: RunStageName) -> RunRecord:
        run = self._require_run(run_id)
        start_index = RUN_STAGE_ORDER[start_stage]
        source_guard_failure = self._ensure_source_is_current(run, start_stage)
        if source_guard_failure is not None:
            return source_guard_failure

        pdf_path = Path(run.source_path)
        run_dir = self._run_dir(run.id)
        run_dir.mkdir(parents=True, exist_ok=True)

        markdown_text: Optional[str] = None
        chunks: Optional[list[str]] = None
        problem: Optional[FormalizedProblem] = None
        route_analysis: Optional[dict[str, Any]] = None
        math_result: Optional[MathResult] = None

        if start_index > RUN_STAGE_ORDER["extract"]:
            markdown_text = self._load_text_artifact(run.id, "extract", "extracted.md")
        if start_index > RUN_STAGE_ORDER["chunk"]:
            chunks = self._load_chunks(run.id)
        if start_index > RUN_STAGE_ORDER["formalize"]:
            problem = self._load_problem(run)
        if start_index > RUN_STAGE_ORDER["route"]:
            route_analysis = self._load_json_artifact(run.id, "solve", "route.json")
        if start_index > RUN_STAGE_ORDER["solve"]:
            math_result = self._load_math_result(run)

        if start_index <= RUN_STAGE_ORDER["validate_input"]:
            self.state_manager.start_stage(run.id, "validate_input")
            try:
                current_fingerprint = self._fingerprint_file(pdf_path)
                validate_pdf(pdf_path)
                self.state_manager.complete_stage(
                    run.id,
                    "validate_input",
                    metadata={
                        "source_path": run.source_path,
                        "source_size_bytes": pdf_path.stat().st_size,
                        "source_fingerprint": current_fingerprint,
                    },
                )
            except Exception as exc:
                self.state_manager.fail_stage(
                    run.id,
                    "validate_input",
                    {"code": "validation_failed", "message": str(exc)},
                )
                return self._require_run(run.id)

        if start_index <= RUN_STAGE_ORDER["extract"]:
            self.state_manager.start_stage(run.id, "extract")
            try:
                extraction_result = self.extractor.extract_with_report(pdf_path)
                markdown_text = extraction_result.text
                extract_artifact = self._write_text_artifact(
                    run.id,
                    stage_name="extract",
                    content=markdown_text,
                    artifact_type="markdown",
                    summary="Normalized extracted markdown/text from source PDF",
                    metadata={"source_path": run.source_path},
                    relative_parts=("extract", "extracted.md"),
                )
                extract_report_artifact = self._write_json_artifact(
                    run.id,
                    stage_name="extract",
                    payload=extraction_result.report.model_dump(mode="json"),
                    artifact_type="json",
                    summary="Extraction diagnostics including extractor choice and warnings",
                    metadata={"extractor_used": extraction_result.report.extractor_used},
                    relative_parts=("extract", "report.json"),
                )
                self.state_manager.complete_stage(
                    run.id,
                    "extract",
                    metadata={
                        "extractor_used": extraction_result.report.extractor_used,
                        "warning_count": len(extraction_result.report.warnings),
                        "normalized_character_count": extraction_result.report.normalized_character_count,
                        "scanned_pdf_suspected": extraction_result.report.scanned_pdf_suspected,
                    },
                    artifacts=[extract_artifact, extract_report_artifact],
                )
            except Exception as exc:
                self.state_manager.fail_stage(
                    run.id,
                    "extract",
                    {"code": "extract_failed", "message": str(exc)},
                )
                return self._require_run(run.id)

        if markdown_text is None:
            raise RunServiceError(f"Run {run.id} is missing extracted text required for chunking")

        if start_index <= RUN_STAGE_ORDER["chunk"]:
            self.state_manager.start_stage(run.id, "chunk")
            try:
                raw_chunks = self.chunker.chunk(markdown_text)
                chunk_report = build_chunk_report(raw_chunks)
                validate_chunk_report(chunk_report)
                chunks = chunk_report.chunk_texts()
                chunk_artifact = self._write_json_artifact(
                    run.id,
                    stage_name="chunk",
                    payload=chunk_report.model_dump(mode="json"),
                    artifact_type="json",
                    summary="Deterministic chunk manifest and chunking diagnostics",
                    metadata={"chunk_count": chunk_report.total_chunks},
                    relative_parts=("chunks", "chunk_report.json"),
                )
                self.state_manager.complete_stage(
                    run.id,
                    "chunk",
                    metadata={
                        "chunk_count": chunk_report.total_chunks,
                        "warning_count": len(chunk_report.warnings),
                        "total_characters": chunk_report.total_characters,
                    },
                    artifacts=[chunk_artifact],
                )
            except Exception as exc:
                self.state_manager.fail_stage(
                    run.id,
                    "chunk",
                    {"code": "chunk_failed", "message": str(exc)},
                )
                return self._require_run(run.id)

        if chunks is None:
            raise RunServiceError(f"Run {run.id} is missing chunks required for formalization")

        if start_index <= RUN_STAGE_ORDER["formalize"]:
            self.state_manager.start_stage(run.id, "formalize")
            try:
                source_document = SourceDocument(
                    format="pdf",
                    uri=run.source_path,
                    title=pdf_path.stem,
                    extracted_text=markdown_text,
                )
                problem, formalization_report = self.formalizer.formalize_with_report(chunks, source_doc=source_document)
                formalization_report_artifact = self._write_json_artifact(
                    run.id,
                    stage_name="formalize",
                    payload=formalization_report.model_dump(mode="json"),
                    artifact_type="json",
                    summary="Formalization report with confidence, ambiguities, and validation result",
                    metadata={"accepted": formalization_report.accepted, "confidence": formalization_report.confidence},
                    relative_parts=("formalized", "formalization_report.json"),
                )

                if problem is None:
                    self.state_manager.fail_stage(
                        run.id,
                        "formalize",
                        {
                            "code": "formalize_refused",
                            "message": formalization_report.refusal_reason or "Formalization was refused",
                        },
                        metadata={
                            "accepted": False,
                            "confidence": formalization_report.confidence,
                            "ambiguity_count": len(formalization_report.ambiguity_notes),
                        },
                        artifacts=[formalization_report_artifact],
                    )
                    return self._require_run(run.id)

                self.state_manager.save_problem(problem)
                problem_artifact = self._write_json_artifact(
                    run.id,
                    stage_name="formalize",
                    payload=problem.model_dump(mode="json"),
                    artifact_type="json",
                    summary="Structured formalized problem payload",
                    metadata={"problem_id": problem.id, "title": problem.title},
                    relative_parts=("formalized", "problem.json"),
                )
                self.state_manager.complete_stage(
                    run.id,
                    "formalize",
                    metadata={
                        "problem_id": problem.id,
                        "title": problem.title,
                        "confidence": formalization_report.confidence,
                        "ambiguity_count": len(formalization_report.ambiguity_notes),
                    },
                    artifacts=[formalization_report_artifact, problem_artifact],
                    problem_id=problem.id,
                )
                problem = self._load_problem(self._require_run(run.id))
            except Exception as exc:
                self.state_manager.fail_stage(
                    run.id,
                    "formalize",
                    {"code": "formalize_failed", "message": str(exc)},
                )
                return self._require_run(run.id)

        if problem is None:
            raise RunServiceError(f"Run {run.id} is missing a formalized problem required for routing")

        if start_index <= RUN_STAGE_ORDER["route"]:
            self.state_manager.start_stage(run.id, "route", problem_id=problem.id)
            try:
                router = self._router_factory()
                route_analysis = router.analyze(problem)
                route_artifact = self._write_json_artifact(
                    run.id,
                    stage_name="route",
                    payload=route_analysis,
                    artifact_type="json",
                    summary="Plugin routing analysis and selection data",
                    metadata={"problem_id": problem.id},
                    relative_parts=("solve", "route.json"),
                )
                if not route_analysis.get("success"):
                    self.state_manager.fail_stage(
                        run.id,
                        "route",
                        route_analysis.get("failure_reason") or {"code": "route_failed", "message": "Routing failed"},
                        metadata=route_analysis,
                        artifacts=[route_artifact],
                        problem_id=problem.id,
                    )
                    return self._require_run(run.id)
                self.state_manager.complete_stage(
                    run.id,
                    "route",
                    metadata=route_analysis,
                    artifacts=[route_artifact],
                    problem_id=problem.id,
                )
            except Exception as exc:
                self.state_manager.fail_stage(
                    run.id,
                    "route",
                    {"code": "route_failed", "message": str(exc)},
                    problem_id=problem.id,
                )
                return self._require_run(run.id)

        if route_analysis is None:
            raise RunServiceError(f"Run {run.id} is missing routing metadata required for solving")

        if start_index <= RUN_STAGE_ORDER["solve"]:
            self.state_manager.start_stage(run.id, "solve", problem_id=problem.id)
            try:
                router = self._router_factory()
                math_result = router.solve_with_analysis(problem, route_analysis)
                result_artifact = self._write_json_artifact(
                    run.id,
                    stage_name="solve",
                    payload=math_result.model_dump(mode="json"),
                    artifact_type="json",
                    summary="Final solver output for the selected plugin",
                    metadata={"problem_id": problem.id, "plugin_used": math_result.plugin_used},
                    relative_parts=("solve", "math_result.json"),
                )
                if not math_result.success:
                    self.state_manager.fail_stage(
                        run.id,
                        "solve",
                        math_result.failure_reason or {"code": "solve_failed", "message": "Math solve failed"},
                        metadata={"plugin_used": math_result.plugin_used},
                        artifacts=[result_artifact],
                        problem_id=problem.id,
                    )
                    return self._require_run(run.id)
                self.state_manager.complete_stage(
                    run.id,
                    "solve",
                    metadata={"plugin_used": math_result.plugin_used, "final_answer": math_result.final_answer},
                    artifacts=[result_artifact],
                    problem_id=problem.id,
                )
            except Exception as exc:
                self.state_manager.fail_stage(
                    run.id,
                    "solve",
                    {"code": "solve_failed", "message": str(exc)},
                    problem_id=problem.id,
                )
                return self._require_run(run.id)

        if math_result is None:
            raise RunServiceError(f"Run {run.id} is missing a math result required for MVP generation")

        if start_index <= RUN_STAGE_ORDER["generate_mvp"]:
            self.state_manager.start_stage(run.id, "generate_mvp", problem_id=problem.id)
            try:
                orchestrator = self._orchestrator_factory(run_dir)
                mvp_output = orchestrator.generate_mvp(math_result)
                self.state_manager.save_mvp(problem.id, math_result.problem_id + "_math", mvp_output)
                mvp_artifacts = self._build_mvp_artifacts(run.id, mvp_output)
                if not self._mvp_passed(mvp_output):
                    self.state_manager.fail_stage(
                        run.id,
                        "generate_mvp",
                        {
                            "code": "mvp_validation_failed",
                            "message": "Generated MVP did not pass guardrail validation.",
                        },
                        metadata={
                            "root_directory": mvp_output.root_directory,
                            "attempt_count": len(mvp_output.attempt_history),
                        },
                        artifacts=mvp_artifacts,
                        problem_id=problem.id,
                    )
                    return self._require_run(run.id)
                self.state_manager.complete_stage(
                    run.id,
                    "generate_mvp",
                    metadata={
                        "root_directory": mvp_output.root_directory,
                        "attempt_count": len(mvp_output.attempt_history),
                    },
                    artifacts=mvp_artifacts,
                    problem_id=problem.id,
                )
            except Exception as exc:
                self.state_manager.fail_stage(
                    run.id,
                    "generate_mvp",
                    {"code": "generate_mvp_failed", "message": str(exc)},
                    problem_id=problem.id,
                )
                return self._require_run(run.id)

        self.state_manager.complete_run(run.id, current_stage="generate_mvp")
        return self._require_run(run.id)

    def _build_router(self) -> Router:
        router = Router(state_manager=self.state_manager)
        register_all_plugins(router)
        return router

    def _build_orchestrator(self, run_dir: Path) -> Orchestrator:
        return Orchestrator(workspace_root=run_dir / "mvp_workspace")

    def _next_stage_to_run(self, run_id: str) -> Optional[RunStageName]:
        stage_status = {record.stage_name: record.status for record in self.state_manager.get_run_stages(run_id)}
        for stage_name, _ in sorted(RUN_STAGE_ORDER.items(), key=lambda item: item[1]):
            status = stage_status.get(stage_name)
            if status in {None, "pending", "failed", "invalidated"}:
                return stage_name
        return None

    def _build_mvp_artifacts(self, run_id: str, mvp_output: MVPOutput) -> list[RunArtifactRef]:
        summary_payload = {
            "problem_id": mvp_output.problem_id,
            "root_directory": mvp_output.root_directory,
            "files": [generated_file.relative_path for generated_file in mvp_output.files],
            "attempt_history": [attempt.model_dump(mode="json") for attempt in mvp_output.attempt_history],
            "guardrail_report": (
                mvp_output.guardrail_report.model_dump(mode="json")
                if mvp_output.guardrail_report is not None
                else None
            ),
        }
        summary_artifact = self._write_json_artifact(
            run_id,
            stage_name="generate_mvp",
            payload=summary_payload,
            artifact_type="json",
            summary="Persisted MVP summary including attempts and guardrail report",
            metadata={"problem_id": mvp_output.problem_id},
            relative_parts=("mvp", "summary.json"),
        )
        workspace_artifact = RunArtifactRef(
            artifact_type="workspace",
            path=mvp_output.root_directory,
            stage_name="generate_mvp",
            summary="Generated MVP workspace root",
            metadata={"file_count": len(mvp_output.files)},
        )
        return [summary_artifact, workspace_artifact]

    def _mvp_passed(self, mvp_output: MVPOutput) -> bool:
        if mvp_output.guardrail_report is None:
            return False
        return bool(
            mvp_output.guardrail_report.overall_pass
            and mvp_output.guardrail_report.math_validation_pass
        )

    def _load_problem(self, run: RunRecord) -> Optional[FormalizedProblem]:
        payload = self._load_json_artifact(run.id, "formalized", "problem.json")
        if payload is not None:
            return FormalizedProblem.model_validate(payload)
        if run.problem_id is None:
            return None
        return self.state_manager.get_problem(run.problem_id)

    def _load_math_result(self, run: RunRecord) -> Optional[MathResult]:
        payload = self._load_json_artifact(run.id, "solve", "math_result.json")
        if payload is not None:
            return MathResult.model_validate(payload)
        if run.problem_id is None:
            return None
        return self.state_manager.get_math_result(run.problem_id)

    def _load_chunks(self, run_id: str) -> Optional[list[str]]:
        chunk_report_payload = self._load_json_artifact(run_id, "chunks", "chunk_report.json")
        if chunk_report_payload is not None:
            return ChunkReport.model_validate(chunk_report_payload).chunk_texts()
        legacy_chunks = self._load_json_artifact(run_id, "chunks", "chunks.json")
        if isinstance(legacy_chunks, list):
            return [str(chunk) for chunk in legacy_chunks]
        return None

    def _write_text_artifact(
        self,
        run_id: str,
        stage_name: RunStageName,
        content: str,
        artifact_type: str,
        summary: str,
        metadata: Optional[dict[str, Any]],
        relative_parts: tuple[str, ...],
    ) -> RunArtifactRef:
        artifact_path = self._artifact_path(run_id, *relative_parts)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(content, encoding="utf-8")
        return RunArtifactRef(
            artifact_type=artifact_type,
            path=str(artifact_path),
            stage_name=stage_name,
            summary=summary,
            metadata=metadata or {},
            content_hash=self._sha256_text(content),
        )

    def _write_json_artifact(
        self,
        run_id: str,
        stage_name: RunStageName,
        payload: Any,
        artifact_type: str,
        summary: str,
        metadata: Optional[dict[str, Any]],
        relative_parts: tuple[str, ...],
    ) -> RunArtifactRef:
        content = json.dumps(payload, indent=2, sort_keys=True)
        return self._write_text_artifact(
            run_id,
            stage_name=stage_name,
            content=content,
            artifact_type=artifact_type,
            summary=summary,
            metadata=metadata,
            relative_parts=relative_parts,
        )

    def _load_text_artifact(self, run_id: str, *relative_parts: str) -> Optional[str]:
        artifact_path = self._artifact_path(run_id, *relative_parts)
        if not artifact_path.exists():
            return None
        return artifact_path.read_text(encoding="utf-8")

    def _load_json_artifact(self, run_id: str, *relative_parts: str) -> Any:
        raw_content = self._load_text_artifact(run_id, *relative_parts)
        if raw_content is None:
            return None
        return json.loads(raw_content)

    def _artifact_path(self, run_id: str, *relative_parts: str) -> Path:
        for part in relative_parts:
            if not part or "/" in part or part in {".", ".."}:
                raise RunServiceError(f"Unsafe run artifact path component: {part}")
        run_root = self._run_dir(run_id).resolve()
        candidate_path = (run_root / Path(*relative_parts)).resolve()
        if candidate_path != run_root and run_root not in candidate_path.parents:
            raise RunServiceError("Resolved artifact path escaped the run directory")
        return candidate_path

    def _ensure_source_is_current(self, run: RunRecord, stage_name: RunStageName) -> Optional[RunRecord]:
        if RUN_STAGE_ORDER[stage_name] > RUN_STAGE_ORDER["extract"]:
            return None

        source_path = Path(run.source_path)
        if not source_path.exists() or not source_path.is_file():
            self.state_manager.fail_stage(
                run.id,
                stage_name,
                {
                    "code": "source_missing",
                    "message": "The original source PDF is missing and this stage cannot be resumed.",
                },
                metadata={"source_path": run.source_path},
                problem_id=run.problem_id,
            )
            return self._require_run(run.id)

        current_fingerprint = self._fingerprint_file(source_path)
        if current_fingerprint != run.source_fingerprint:
            self.state_manager.fail_stage(
                run.id,
                stage_name,
                {
                    "code": "stale_source",
                    "message": "The source PDF has changed since this run was created. Retry with a new run.",
                },
                metadata={
                    "source_path": run.source_path,
                    "expected_fingerprint": run.source_fingerprint,
                    "actual_fingerprint": current_fingerprint,
                },
                problem_id=run.problem_id,
            )
            return self._require_run(run.id)
        return None

    def _run_dir(self, run_id: str) -> Path:
        return self.runs_root / run_id

    def _fingerprint_file(self, file_path: Path) -> str:
        hasher = hashlib.sha256()
        with file_path.open("rb") as handle:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()

    def _sha256_text(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _require_run(self, run_id: str) -> RunRecord:
        run = self.state_manager.get_run(run_id)
        if run is None:
            raise RunServiceError(f"Run not found: {run_id}")
        return run
