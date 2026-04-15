#!/usr/bin/env python3
"""Minimal CLI for the research engine — Phase 0 proof of concept."""


import argparse
import sys
from pathlib import Path

from engine.state import FormalizedProblem, SourceDocument, MathResult, MVPOutput
from ingestion.pipeline import IngestionPipeline
from math_engine.plugins.calculus.plugin import CalculusPlugin
from math_engine.router import Router
from mvp_generator.orchestrator import Orchestrator
from helicops_critic.integration import HelicOpsIntegration


def run_pipeline(pdf_path: str) -> None:
    """Run full end-to-end pipeline: Ingest -> Solve -> MVP."""
    # 1. Ingest
    print(f"[*] Ingesting {pdf_path}...")
    ingestion = IngestionPipeline()
    problem = ingestion.process(Path(pdf_path))
    
    # 2. Solve
    print(f"[*] Solving problem: {problem.title}...")
    router = Router()
    router.register(CalculusPlugin())
    math_result = router.route(problem)
    
    if not math_result.success:
        print(f"[!] Math Engine failed: {math_result.failure_reason}")
        return

    # 3. Generate MVP
    print(f"[*] Generating MVP with Agent Swarm + HelicOps Critic...")
    orchestrator = Orchestrator()
    mvp_output = orchestrator.generate_mvp(math_result)
    
    print("\n" + "="*50)
    print(f"PIPELINE COMPLETE")
    print(f"MVP Location: {mvp_output.root_directory}")
    print(f"Guardrail Status: {'PASS' if mvp_output.guardrail_report.overall_pass else 'FAIL'}")
    print(f"Math Validation: {'PASS' if mvp_output.guardrail_report.math_validation_pass else 'FAIL'}")
    if mvp_output.guardrail_report.violations:
        print(f"Violations: {len(mvp_output.guardrail_report.violations)}")
    print("="*50)


def ingest(pdf_path: str) -> None:
    """Ingest a PDF research paper and output the FormalizedProblem as JSON."""
    pipeline = IngestionPipeline()
    problem = pipeline.process(Path(pdf_path))
    print(problem.model_dump_json(indent=2))


def solve(latex: str) -> None:
    """Solve a calculus expression and print the MathResult as JSON."""
    problem = FormalizedProblem(
        source_document=SourceDocument(format="unknown"),
        title="CLI calculus problem",
        domain_tags=["calculus"],
        objective=latex,
        metadata={"calculus_params": {}},
    )

    router = Router()
    router.register(CalculusPlugin())
    result = router.route(problem)

    print(result.model_dump_json(indent=2))
    sys.exit(0 if result.success else 1)


def helicops_status() -> None:
    """Check HelicOps integration status."""
    integration = HelicOpsIntegration()
    info = integration.get_guardrail_info()
    
    print("=" * 50)
    print("HELICOPS INTEGRATION STATUS")
    print("=" * 50)
    
    if info.get("available"):
        print(f"Status: ✅ Available")
        print(f"Guardrails: {info.get('count', 0)}")
        print("\nAvailable Guardrails:")
        for g in info.get("guardrails", [])[:10]:  # Show first 10
            print(f"  - {g.get('id')} ({g.get('severity', 'unknown')})")
        if len(info.get("guardrails", [])) > 10:
            print(f"  ... and {len(info.get('guardrails', [])) - 10} more")
    else:
        print("Status: ❌ Unavailable")
        print("HelicOps guardrails will run in mock mode (always pass)")
        print("\nTo enable:")
        print("  pip install -e ~/Desktop/HelicOps/packages/core")
        print("  pip install -e ~/Desktop/HelicOps/packages/py")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Research Engine — Phase 0 CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    solve_parser = subparsers.add_parser("solve", help="Solve a math problem")
    solve_parser.add_argument(
        "latex",
        help="LaTeX expression (e.g., '\\\\frac{d}{dx} x^3')",
    )

    ingest_parser = subparsers.add_parser("ingest", help="Ingest a research paper")
    ingest_parser.add_argument(
        "pdf",
        help="Path to the research paper PDF",
    )

    pipeline_parser = subparsers.add_parser("pipeline", help="Run full end-to-end pipeline")
    pipeline_parser.add_argument(
        "pdf",
        help="Path to the research paper PDF",
    )
    
    subparsers.add_parser("helicops-status", help="Check HelicOps integration status")

    args = parser.parse_args()
    if args.command == "solve":
        solve(args.latex)
    elif args.command == "ingest":
        ingest(args.pdf)
    elif args.command == "pipeline":
        run_pipeline(args.pdf)
    elif args.command == "helicops-status":
        helicops_status()


if __name__ == "__main__":
    main()
