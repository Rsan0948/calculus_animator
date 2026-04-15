#!/usr/bin/env python3
"""Research Engine CLI — automated mathematical problem solving and code generation."""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, List, Optional

from engine.repo_inventory import get_repo_surface_inventory
from engine.run_service import DEFAULT_RUNS_ROOT, RunService, RunServiceError
from engine.state import (
    ChunkReport,
    ExtractionReport,
    FormalizationReport,
    FormalizedProblem,
    RUN_STAGE_SEQUENCE,
    RunStageRecord,
    SourceDocument,
)
from engine.state_manager import StateManager
from helicops_critic.integration import HelicOpsIntegration
from ingestion.pipeline import IngestionPipeline
from math_engine.plugin_registry import get_plugin_capabilities, register_all_plugins
from math_engine.router import Router
from mvp_generator.orchestrator import Orchestrator


SOLVE_HELP = """
Solve a math problem using the appropriate domain plugin.

EXAMPLES:
  # Calculus
  research-engine solve "derivative of x^3"
  research-engine solve "integral of x^2"

  # Linear Algebra
  research-engine solve "eigenvalues of [[1,2],[3,4]]"

  # Statistics
  research-engine solve "mean of [1,2,3,4,5]"

  # Number Theory
  research-engine solve "is 97 prime"
  research-engine solve "gcd of 48 and 18"

  # Combinatorics
  research-engine solve "combinations of 10 choose 3"

  # Graph Theory
  research-engine solve "shortest path from A to E"

  # Logic
  research-engine solve "simplify (p & q) | (p & ~q)"

The engine auto-detects the domain from your input.
"""

INGEST_HELP = """
Ingest a research paper PDF and extract the mathematical problem.

EXAMPLES:
  research-engine ingest paper.pdf
  research-engine ingest ~/papers/calculus-proof.pdf

The paper will be:
  1. Extracted to markdown
  2. Chunked into sections
  3. Formalized into a structured problem
  4. Saved to the database for processing
"""

RUN_HELP = """
Run the first-class persisted workflow for one research paper.

EXAMPLES:
  research-engine run paper.pdf

This creates a durable run with stage state, artifacts, and resume support.
"""

PIPELINE_HELP = """
Run the full end-to-end pipeline: Ingest -> Solve -> Generate MVP.

EXAMPLES:
  research-engine pipeline paper.pdf

This is a compatibility wrapper around `research-engine run`.
"""

RUNS_HELP = """
List persisted workflow runs.

EXAMPLES:
  research-engine runs
"""

SHOW_RUN_HELP = """
Show detailed stage history for a persisted run.

EXAMPLES:
  research-engine show-run <run-id>
"""

RESUME_HELP = """
Resume the first failed or incomplete stage for a run.

EXAMPLES:
  research-engine resume <run-id>
"""

RETRY_STAGE_HELP = """
Invalidate one stage and rerun from that point onward.

EXAMPLES:
  research-engine retry-stage <run-id> formalize
"""

LIST_HELP = """
List all processed problems in the database.

EXAMPLES:
  research-engine list                    # All problems
  research-engine list --status solved    # Only solved
  research-engine list --status failed    # Only failed
  research-engine list --status pending   # Waiting to be solved
"""

SHOW_HELP = """
Show detailed information about a specific problem.

EXAMPLES:
  research-engine show <problem-id>
  research-engine show abc-123-def
"""

DOMAINS_HELP = """
Show current domain support status for the product path.

EXAMPLES:
  research-engine domains
"""

SURFACES_HELP = """
Show the current repo surface map for the migration.

EXAMPLES:
  research-engine surfaces
"""

CLEANUP_HELP = """
Clean up old problems and temporary files.

WARNING: This permanently deletes data.

EXAMPLES:
  research-engine cleanup --confirm    # Delete everything
"""

QUICKSTART_HELP = """
Interactive quick-start guide for new users.

This command will:
  1. Check your environment setup
  2. Run a demo calculation
  3. Show you next steps

EXAMPLES:
  research-engine quickstart
"""


def detect_domain(objective: str) -> List[str]:
    """Detect math domain from objective string."""
    lowered_objective = objective.lower()

    if any(keyword in lowered_objective for keyword in ["derivative", "integral", "limit", "dx", "dy", "∫", "∂"]):
        return ["calculus"]
    if any(keyword in lowered_objective for keyword in ["matrix", "eigenvalue", "determinant", "vector", "eigen"]):
        return ["linear_algebra"]
    if any(keyword in lowered_objective for keyword in ["mean", "std", "variance", "correlation", "regression", "distribution", "hypothesis"]):
        return ["statistics"]
    if any(keyword in lowered_objective for keyword in ["minimize", "maximize", "optimize", "constraint", "linear program"]):
        return ["optimization"]
    if any(keyword in lowered_objective for keyword in ["prime", "gcd", "lcm", "factor", "modular", "totient"]):
        return ["number_theory"]
    if any(keyword in lowered_objective for keyword in ["permutation", "combination", "binomial", "factorial", "catalan", "bell"]):
        return ["combinatorics"]
    if any(keyword in lowered_objective for keyword in ["graph", "shortest path", "network", "connected component", "flow"]):
        return ["graph_theory"]
    if any(keyword in lowered_objective for keyword in ["logic", "boolean", "sat", "satisfiable", "truth table", "proposition", "simplify"]):
        return ["logic"]
    return ["calculus"]


def _validate_pdf_path(pdf_path_str: str) -> Path:
    """Validate PDF path exists and is a file."""
    path = Path(pdf_path_str).resolve()
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path_str}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {pdf_path_str}")
    return path


def _format_run_error(error: object) -> str:
    if isinstance(error, dict):
        return str(error.get("message", error))
    return str(error)


def _print_run_summary(run_id: str) -> None:
    state = StateManager()
    run = state.get_run(run_id)
    if run is None:
        print(f"Run not found: {run_id}")
        return

    print(f"Run ID: {run.id}")
    print(f"Status: {run.status}")
    print(f"Current Stage: {run.current_stage or 'n/a'}")
    print(f"Source: {run.source_path}")
    if run.problem_id:
        print(f"Problem ID: {run.problem_id}")
    if run.last_error:
        print(f"Last Error: {_format_run_error(run.last_error)}")


def run_document(pdf_path_str: str, command_name: str = "run") -> None:
    """Run the first-class persisted workflow for one PDF."""
    try:
        pdf_path = _validate_pdf_path(pdf_path_str)
        service = RunService()
        run = service.run_pdf(pdf_path, command_name=command_name)
        _print_run_summary(run.id)

        if run.status == "completed":
            mvp_output = StateManager().get_mvp(run.problem_id) if run.problem_id else None
            if mvp_output is not None:
                print(f"MVP Workspace: {mvp_output.root_directory}")
            print("✅ Run completed")
            return

        print(f"❌ Run failed during {run.current_stage or 'unknown stage'}")
    except Exception as exc:
        print(f"❌ Run failed: {exc}")
        print("\n💡 Run with --verbose for details")
        if logging.getLogger().level == logging.DEBUG:
            raise


def run_pipeline(pdf_path_str: str) -> None:
    """Compatibility wrapper for the old pipeline command."""
    run_document(pdf_path_str, command_name="pipeline")


def resume_run(run_id: str) -> None:
    """Resume a failed or incomplete run."""
    try:
        service = RunService()
        run = service.resume_run(run_id)
        _print_run_summary(run.id)
        if run.status == "completed":
            print("✅ Run completed")
            return
        print(f"❌ Run is still incomplete at {run.current_stage or 'unknown stage'}")
    except RunServiceError as exc:
        print(f"❌ {exc}")
    except Exception as exc:
        print(f"❌ Resume failed: {exc}")
        if logging.getLogger().level == logging.DEBUG:
            raise


def retry_stage(run_id: str, stage_name: str) -> None:
    """Retry a specific stage and invalidate downstream state."""
    try:
        service = RunService()
        run = service.retry_stage(run_id, stage_name)  # type: ignore[arg-type]
        _print_run_summary(run.id)
        if run.status == "completed":
            print("✅ Run completed")
            return
        print(f"❌ Run is still incomplete at {run.current_stage or 'unknown stage'}")
    except RunServiceError as exc:
        print(f"❌ {exc}")
    except Exception as exc:
        print(f"❌ Retry failed: {exc}")
        if logging.getLogger().level == logging.DEBUG:
            raise


def ingest(pdf_path_str: str) -> None:
    """Ingest a PDF research paper and store the formalized problem."""
    try:
        pdf_path = _validate_pdf_path(pdf_path_str)
        state_manager = StateManager()
        pipeline = IngestionPipeline(state_manager=state_manager)
        problem = pipeline.process(pdf_path)
        print(f"✓ Ingested: {problem.title}")
        print(f"  ID: {problem.id}")
        print(f"  Domains: {', '.join(problem.domain_tags)}")
        print("  Status: Saved to database")
    except Exception as exc:
        print(f"❌ Ingestion failed: {exc}")
        print("\n💡 Run with --verbose for details")


def solve(expression: str) -> None:
    """Solve a math expression."""
    try:
        state_manager = StateManager()
        domain_tags = detect_domain(expression)
        problem = FormalizedProblem(
            source_document=SourceDocument(format="unknown"),
            title=f"CLI {domain_tags[0]} problem",
            domain_tags=domain_tags,
            objective=expression,
        )
        state_manager.save_problem(problem)

        router = Router(state_manager=state_manager)
        register_all_plugins(router)
        result = router.route(problem)

        if result.success:
            print(f"✅ {result.final_answer}")
            if result.steps:
                print(f"\nSteps ({len(result.steps)}):")
                for step in result.steps[:3]:
                    print(f"  {step.step_number}. {step.title}: {step.description}")
                if len(result.steps) > 3:
                    print(f"  ... and {len(result.steps) - 3} more")
            return

        print(f"❌ Could not solve: {result.failure_reason}")
        print("\n💡 Tip: Try a different input format")
        print("   Example: 'eigenvalues of [[1,2],[3,4]]'")
    except Exception as exc:
        print(f"❌ Error: {exc}")
        print("\n💡 Run with --verbose for details")
        if logging.getLogger().level == logging.DEBUG:
            raise


def show_domains() -> None:
    """Show domain support maturity for the current product path."""
    capabilities = get_plugin_capabilities()
    print("=" * 72)
    print("DOMAIN SUPPORT")
    print("=" * 72)
    print(f"{'Domain':<18} {'Status':<13} {'Recommended Input'}")
    print("-" * 72)
    for plugin_name in sorted(capabilities):
        capability = capabilities[plugin_name]
        status = str(capability.get("status", "unknown"))
        recommended_input = str(capability.get("recommended_input", "Unknown"))
        print(f"{plugin_name:<18} {status:<13} {recommended_input}")
    print("\nStatus meanings:")
    print("  reliable      Strong current support on the CLI golden path")
    print("  beta          Supported, but still being tightened")
    print("  experimental  Present in the registry, but not ready to rely on")


def show_surfaces() -> None:
    """Show active, transitional, and legacy repo surfaces."""
    inventory = get_repo_surface_inventory()
    titles = {
        "active": "ACTIVE PRODUCT PATH",
        "transitional": "TRANSITIONAL SURFACES",
        "legacy": "LEGACY SURFACES",
    }

    for classification in ("active", "transitional", "legacy"):
        print("=" * 72)
        print(titles[classification])
        print("=" * 72)
        print(f'{"Path":<24} {"Role"}')
        print("-" * 72)
        for surface in inventory[classification]:
            print(f'{surface["path"]:<24} {surface["role"]}')
        print()

    print("Status meanings:")
    print("  active        Primary research-engine product path")
    print("  transitional  Still referenced or useful during the migration")
    print("  legacy        Older app surfaces outside the current product boundary")


def helicops_status() -> None:
    """Check HelicOps integration status."""
    integration = HelicOpsIntegration()
    info = integration.get_guardrail_info()

    print("=" * 50)
    print("HELICOPS INTEGRATION STATUS")
    print("=" * 50)

    if info.get("available"):
        print("Status: ✅ Available")
        print(f"Guardrails: {info.get('count', 0)}")
        print("\nAvailable Guardrails:")
        for guardrail in info.get("guardrails", [])[:10]:
            print(f"  - {guardrail.get('id')} ({guardrail.get('severity', 'unknown')})")
        remaining = len(info.get("guardrails", [])) - 10
        if remaining > 0:
            print(f"  ... and {remaining} more")
        return

    print("Status: ❌ Unavailable")
    print("\nTo enable:")
    print("  pip install -e ~/Desktop/HelicOps/packages/core")
    print("  pip install -e ~/Desktop/HelicOps/packages/py")


def list_runs() -> None:
    """List persisted run records."""
    runs = RunService().list_runs()
    if not runs:
        print("No runs found.")
        return

    print(f"{'Run ID':<36} {'Status':<12} {'Stage':<18} {'Source':<30}")
    print("-" * 104)
    for run in runs:
        source_name = Path(run.source_path).name
        print(f"{run.id:<36} {run.status:<12} {(run.current_stage or ''):<18} {source_name:<30}")


def _safe_run_artifact_path(run_id: str, *parts: str) -> Path | None:
    if not run_id or any(sep in run_id for sep in ('/', '\\')) or run_id in {'.', '..'}:
        return None

    normalized_parts: list[str] = []
    for part in parts:
        if not part or any(sep in part for sep in ('/', '\\')) or part in {'.', '..'}:
            return None
        normalized_parts.append(part)

    root = DEFAULT_RUNS_ROOT.resolve()
    candidate = (root / run_id / Path(*normalized_parts)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _load_run_artifact_json(run_id: str, *parts: str) -> dict[str, Any] | None:
    artifact_path = _safe_run_artifact_path(run_id, *parts)
    if artifact_path is None or not artifact_path.exists() or not artifact_path.is_file():
        return None
    try:
        payload = json.loads(artifact_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _print_stage_summary(run_id: str, stage: RunStageRecord) -> None:
    if stage.stage_name == 'validate_input':
        source_size = stage.metadata.get('source_size_bytes')
        if source_size is not None:
            print(f"  Source Size: {source_size} bytes")
        fingerprint = stage.metadata.get('source_fingerprint')
        if fingerprint:
            print(f"  Fingerprint: {fingerprint}")
        return

    if stage.stage_name == 'extract':
        payload = _load_run_artifact_json(run_id, 'extract', 'report.json')
        if payload is None:
            return
        report = ExtractionReport.model_validate(payload)
        print(f"  Extractor: {report.extractor_used}")
        print(f"  Normalized Characters: {report.normalized_character_count}")
        if report.page_count is not None:
            print(f"  Pages: {report.page_count}")
        if report.fallback_attempts:
            print(f"  Fallback Attempts: {', '.join(report.fallback_attempts)}")
        if report.scanned_pdf_suspected:
            print('  Warning: scanned/image-heavy PDF suspected')
        for warning in report.warnings[:3]:
            print(f"  Warning: {warning}")
        if len(report.warnings) > 3:
            print(f"  Warning: ... and {len(report.warnings) - 3} more")
        return

    if stage.stage_name == 'chunk':
        payload = _load_run_artifact_json(run_id, 'chunks', 'chunk_report.json')
        if payload is None:
            return
        report = ChunkReport.model_validate(payload)
        print(f"  Chunks: {report.total_chunks}")
        print(f"  Total Characters: {report.total_characters}")
        print(f"  Average Chunk Size: {report.average_chunk_size:.1f}")
        print(f"  Dropped Empty Chunks: {report.dropped_empty_chunks}")
        for warning in report.warnings[:3]:
            print(f"  Warning: {warning}")
        if len(report.warnings) > 3:
            print(f"  Warning: ... and {len(report.warnings) - 3} more")
        return

    if stage.stage_name == 'formalize':
        payload = _load_run_artifact_json(run_id, 'formalized', 'formalization_report.json')
        if payload is None:
            return
        report = FormalizationReport.model_validate(payload)
        print(f"  Accepted: {'yes' if report.accepted else 'no'}")
        print(f"  Confidence: {report.confidence:.2f}")
        print(f"  Ambiguities: {len(report.ambiguity_notes)}")
        if report.refusal_reason:
            print(f"  Refusal Reason: {report.refusal_reason}")
        for assumption in report.assumptions[:3]:
            print(f"  Assumption: {assumption}")
        if len(report.assumptions) > 3:
            print(f"  Assumption: ... and {len(report.assumptions) - 3} more")
        for error in report.validation_errors[:3]:
            print(f"  Validation Error: {error}")
        if len(report.validation_errors) > 3:
            print(f"  Validation Error: ... and {len(report.validation_errors) - 3} more")


def show_run(run_id: str) -> None:
    """Show the detailed execution state for a persisted run."""
    state = StateManager()
    run = state.get_run(run_id)
    if run is None:
        print(f"Run not found: {run_id}")
        return

    print("=" * 72)
    print("RUN DETAILS")
    print("=" * 72)
    print(f"Run ID: {run.id}")
    print(f"Command: {run.command_name}")
    print(f"Status: {run.status}")
    print(f"Current Stage: {run.current_stage or 'n/a'}")
    print(f"Source: {run.source_path}")
    if run.problem_id:
        print(f"Problem ID: {run.problem_id}")
    print(f"Created: {run.created_at.isoformat(timespec='seconds')}")
    print(f"Updated: {run.updated_at.isoformat(timespec='seconds')}")
    if run.last_error:
        print(f"Last Error: {_format_run_error(run.last_error)}")

    stages = state.get_run_stages(run_id)
    if not stages:
        return

    print("\n" + "=" * 72)
    print("STAGES")
    print("=" * 72)
    print(f"{'Stage':<18} {'Status':<12} {'Artifacts':<10} {'Started'}")
    print("-" * 72)
    for stage in stages:
        started_at = stage.started_at.isoformat(timespec="seconds") if stage.started_at else ""
        print(f"{stage.stage_name:<18} {stage.status:<12} {len(stage.artifacts):<10} {started_at}")
        if stage.error:
            print(f"  Error: {_format_run_error(stage.error)}")
        _print_stage_summary(run_id, stage)


def list_problems(status: Optional[str] = None) -> None:
    """List all processed problems."""
    state = StateManager()
    problems = state.list_problems(status)

    if not problems:
        print("No problems found.")
        return

    print(f"{'ID':<36} {'Status':<12} {'Created':<20} {'Title':<40}")
    print("-" * 110)
    for problem in problems:
        title = problem["title"][:37] + "..." if len(problem["title"]) > 40 else problem["title"]
        created = problem["created_at"][:19] if problem["created_at"] else ""
        print(f"{problem['id']:<36} {problem['status']:<12} {created:<20} {title:<40}")


def show_problem(problem_id: str) -> None:
    """Show details of a specific problem."""
    state = StateManager()
    problem_record = state.get_problem_record(problem_id)
    if not problem_record:
        print(f"Problem not found: {problem_id}")
        return

    problem = state.get_problem(problem_id)
    if problem is None:
        print(f"Problem could not be reconstructed: {problem_id}")
        return

    print("=" * 50)
    print("PROBLEM DETAILS")
    print("=" * 50)
    print(f"ID: {problem.id}")
    print(f"Title: {problem.title}")
    print(f"Status: {problem_record.get('status', 'unknown')}")
    print(f"Domains: {', '.join(problem.domain_tags)}")
    print(f"Objective: {problem.objective}")

    math_result = state.get_math_result(problem_id)
    if math_result is not None:
        print("\n" + "=" * 50)
        print("MATH RESULT")
        print("=" * 50)
        print(f"Plugin: {math_result.plugin_used}")
        print(f"Success: {'✅' if math_result.success else '❌'}")
        if math_result.success:
            print(f"Answer: {math_result.final_answer}")
            if math_result.steps:
                print(f"\nSteps ({len(math_result.steps)}):")
                for step in math_result.steps:
                    print(f"  {step.step_number}. {step.title}: {step.description}")
        else:
            print(f"Failure: {_format_run_error(math_result.failure_reason)}")

    mvp_output = state.get_mvp(problem_id)
    if mvp_output is not None:
        print("\n" + "=" * 50)
        print("MVP OUTPUT")
        print("=" * 50)
        print(f"Workspace: {mvp_output.root_directory}")
        print(f"Files: {len(mvp_output.files)}")
        if mvp_output.attempt_history:
            latest_attempt = mvp_output.attempt_history[-1]
            print(f"Attempts: {len(mvp_output.attempt_history)} (last violations: {latest_attempt.violation_count})")
        if mvp_output.guardrail_report is not None:
            print(
                "Guardrails: "
                f"{'PASS' if mvp_output.guardrail_report.overall_pass else 'FAIL'}"
            )


def cleanup(confirm: bool = False) -> None:
    """Clean up old data."""
    if not confirm:
        print("WARNING: This will delete all problems from the database.")
        print("Run with --confirm to proceed.")
        return

    db_path = StateManager().db_path
    if db_path.exists():
        db_path.unlink()
        print("✓ Database deleted.")
        return

    print("Database not found.")


def quickstart() -> None:
    """Run interactive quickstart guide."""
    print("Research Engine Quickstart")
    print("=" * 50)

    from startup_checks import validate

    if not validate():
        return

    print("\n[Step 2/3] Running a demo calculation...")
    print("Expression: 'derivative of x^3'")
    solve("derivative of x^3")

    print("\n[Step 3/3] Next steps:")
    print("  • Try solving your own expression: research-engine solve '...'")
    print("  • Run the persisted workflow: research-engine run paper.pdf")
    print("  • Resume or inspect workflow state: research-engine runs / show-run <id>")
    print("  • Check domain maturity: research-engine domains")
    print("  • Inspect repo boundaries: research-engine surfaces")
    print("  • View problem history: research-engine list")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="research-engine",
        description="Automated mathematical problem solving and code generation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    solve_parser = subparsers.add_parser(
        "solve",
        help="Solve a math problem",
        description=SOLVE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    solve_parser.add_argument("expression", help="Math expression to solve")

    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Extract problem from PDF",
        description=INGEST_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ingest_parser.add_argument("pdf", help="Path to research paper PDF")

    run_parser = subparsers.add_parser(
        "run",
        help="Run the persisted workflow",
        description=RUN_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    run_parser.add_argument("pdf", help="Path to research paper PDF")

    pipeline_parser = subparsers.add_parser(
        "pipeline",
        help="Run full end-to-end pipeline",
        description=PIPELINE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pipeline_parser.add_argument("pdf", help="Path to research paper PDF")

    subparsers.add_parser(
        "runs",
        help="List persisted runs",
        description=RUNS_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    show_run_parser = subparsers.add_parser(
        "show-run",
        help="Show run details",
        description=SHOW_RUN_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    show_run_parser.add_argument("run_id", help="Run ID to show")

    resume_parser = subparsers.add_parser(
        "resume",
        help="Resume a failed run",
        description=RESUME_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    resume_parser.add_argument("run_id", help="Run ID to resume")

    retry_stage_parser = subparsers.add_parser(
        "retry-stage",
        help="Retry one run stage",
        description=RETRY_STAGE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    retry_stage_parser.add_argument("run_id", help="Run ID to retry")
    retry_stage_parser.add_argument("stage_name", choices=list(RUN_STAGE_SEQUENCE), help="Stage to rerun")

    subparsers.add_parser(
        "domains",
        help="Show current domain support status",
        description=DOMAINS_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers.add_parser(
        "surfaces",
        help="Show repo surface map",
        description=SURFACES_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers.add_parser(
        "helicops-status",
        help="Check HelicOps integration status",
        description="Check HelicOps integration status.",
    )

    list_parser = subparsers.add_parser(
        "list",
        help="List processed problems",
        description=LIST_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    list_parser.add_argument(
        "--status",
        choices=["pending", "solving", "solved", "failed"],
        help="Filter by status",
    )

    show_parser = subparsers.add_parser(
        "show",
        help="Show problem details",
        description=SHOW_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    show_parser.add_argument("problem_id", help="Problem ID to show")

    cleanup_parser = subparsers.add_parser(
        "cleanup",
        help="Clean up old problems",
        description=CLEANUP_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    cleanup_parser.add_argument("--confirm", action="store_true", help="Confirm deletion")

    subparsers.add_parser(
        "quickstart",
        help="Interactive setup guide",
        description=QUICKSTART_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        )
    else:
        logging.basicConfig(level=logging.WARNING)

    from startup_checks import CommandValidator

    success, missing = CommandValidator.validate_for_command(args.command)
    if not success:
        print(f"❌ This command requires: {', '.join(missing)}")
        print("\nTo fix:")
        for requirement in missing:
            if "Gemini CLI or GOOGLE_API_KEY" in requirement:
                print("  install gemini CLI  # or: export GOOGLE_API_KEY=your-key")
            elif "GOOGLE_API_KEY" in requirement:
                print("  export GOOGLE_API_KEY=your-key")
            elif "marker" in requirement or "extractor" in requirement:
                print("  pip install marker-pdf  # or: pip install pymupdf")
            elif "helicops" in requirement:
                print("  pip install -e ~/Desktop/HelicOps/packages/py")
        sys.exit(1)

    if args.command == "solve":
        solve(args.expression)
    elif args.command == "ingest":
        ingest(args.pdf)
    elif args.command == "run":
        run_document(args.pdf)
    elif args.command == "pipeline":
        run_pipeline(args.pdf)
    elif args.command == "runs":
        list_runs()
    elif args.command == "show-run":
        show_run(args.run_id)
    elif args.command == "resume":
        resume_run(args.run_id)
    elif args.command == "retry-stage":
        retry_stage(args.run_id, args.stage_name)
    elif args.command == "domains":
        show_domains()
    elif args.command == "surfaces":
        show_surfaces()
    elif args.command == "helicops-status":
        helicops_status()
    elif args.command == "list":
        list_problems(args.status)
    elif args.command == "show":
        show_problem(args.problem_id)
    elif args.command == "cleanup":
        cleanup(args.confirm)
    elif args.command == "quickstart":
        quickstart()


if __name__ == "__main__":
    main()
