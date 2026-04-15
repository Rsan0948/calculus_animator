"""Orchestrator for the AI Agent Swarm with HelicOps Critic feedback loop."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from engine.state import GeneratedFile, MathResult, MVPOutput, GuardrailReport
from mvp_generator.agents.architect import ArchitectAgent
from mvp_generator.agents.algorithm import AlgorithmAgent
from mvp_generator.agents.tester import TesterAgent
from mvp_generator.agents.integrator import IntegratorAgent
from helicops_critic.runner import HelicOpsCritic

logger = logging.getLogger(__name__)


class Orchestrator:
    """Coordinates the swarm to produce a validated MVP from a MathResult.
    
    The orchestrator runs an actor-critic loop:
    1. Agents generate code (actor)
    2. HelicOps critic audits (critic)
    3. If violations, agents fix based on feedback
    4. Repeat until pass or max_retries
    """

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path("/tmp/research_engine/mvp")
        self.architect = ArchitectAgent()
        self.algorithm = AlgorithmAgent()
        self.tester = TesterAgent()
        self.integrator = IntegratorAgent()
        self.critic = HelicOpsCritic()

    def generate_mvp(self, math_result: MathResult, max_retries: int = 5) -> MVPOutput:
        """Runs the multi-agent swarm pipeline with a HelicOps critic loop."""
        
        workspace_path = self.workspace_root / math_result.problem_id
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        implemented_code: Dict[str, str] = {}
        report: Optional[GuardrailReport] = None
        
        for attempt in range(1, max_retries + 1):
            logger.info("=" * 50)
            logger.info("Swarm: Build attempt %d/%d...", attempt, max_retries)
            logger.info("=" * 50)
            
            # If we have violations from previous attempt, pass feedback to agents
            violation_feedback = None
            if report and not report.overall_pass:
                violation_feedback = self._format_violations_for_agents(report)
                logger.info("Feedback for retry:\n%s", violation_feedback)
            
            # 1. Architecture Design (only on first attempt, or if architect violations)
            if attempt == 1 or self._has_architect_violations(report):
                logger.info("Step 1: Architecture design...")
                design_manifest = self.architect.design(math_result)
                logger.info("Designed %d files", len(design_manifest))
            
            # 2. Implementation with feedback
            logger.info("Step 2: Algorithm implementation...")
            for file_path, purpose in design_manifest.items():
                if "solver" in file_path or "main" in file_path or "__init__" in file_path:
                    # Check if we already have this file and need to fix it
                    existing_code = implemented_code.get(file_path) if attempt > 1 else None
                    
                    code = self.algorithm.implement(
                        math_result, 
                        file_path, 
                        purpose,
                        existing_code=existing_code,
                        violation_feedback=violation_feedback
                    )
                    implemented_code[file_path] = code
                    logger.info("  Generated: %s", file_path)
            
            # 3. Test Generation
            logger.info("Step 3: Test generation...")
            test_code = self.tester.write_tests(
                math_result, 
                implemented_code,
                violation_feedback=violation_feedback if self._has_tester_violations(report) else None
            )
            implemented_code["tests/test_solver.py"] = test_code
            
            # 4. Final Integration
            logger.info("Step 4: Integration...")
            final_files = self.integrator.finalize(
                math_result, 
                implemented_code,
                violation_feedback=violation_feedback if self._has_integrator_violations(report) else None
            )
            implemented_code.update(final_files)
            
            # Write files to disk for critic
            self._write_to_disk(workspace_path, implemented_code)
            logger.info("Written %d files to %s", len(implemented_code), workspace_path)
            
            # 5. Critic: HelicOps Audit + Math Validation
            logger.info("Step 5: HelicOps critic audit...")
            report = self.critic.audit(workspace_path, math_result)
            
            logger.info("Audit results:")
            logger.info("  Overall Pass: %s", report.overall_pass)
            logger.info("  Math Validation: %s", report.math_validation_pass)
            logger.info("  Violations: %d", len(report.violations))
            
            for v in report.violations:
                logger.info("    - [%s] %s: %s", v.severity, v.check_id, v.message[:80])
            
            if report.overall_pass and report.math_validation_pass:
                logger.info("=" * 50)
                logger.info("SUCCESS! MVP passed all guardrails and validation.")
                logger.info("=" * 50)
                break
            elif attempt == max_retries:
                logger.warning("Max retries reached. Returning best effort.")
            else:
                # Get agent assignments for targeted fixes
                agent_assignments = self.critic.get_violations_by_agent(report)
                logger.info("Retry assignments: %s", 
                           {k: len(v) for k, v in agent_assignments.items() if v})
        
        # Convert to MVPOutput
        generated_files = [
            GeneratedFile(relative_path=p, content=c) 
            for p, c in implemented_code.items()
        ]
        
        return MVPOutput(
            problem_id=math_result.problem_id,
            root_directory=str(workspace_path),
            files=generated_files,
            guardrail_report=report
        )

    def _write_to_disk(self, root: Path, files: Dict[str, str]) -> None:
        """Write generated files to the workspace."""
        for rel_path, content in files.items():
            full_path = root / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
    
    def _format_violations_for_agents(self, report: GuardrailReport) -> str:
        """Format violations as feedback for agents."""
        lines = ["\n=== HELICOPS VIOLATIONS (FIX THESE) ==="]
        for v in report.violations:
            lines.append(f"\n[{v.severity.upper()}] {v.check_id}")
            if v.file_path:
                lines.append(f"  File: {v.file_path}:{v.line_number or '?'}")
            lines.append(f"  Issue: {v.message}")
            if v.fix_suggestion:
                lines.append(f"  Fix: {v.fix_suggestion}")
        lines.append("\n=== END VIOLATIONS ===\n")
        return "\n".join(lines)
    
    def _has_architect_violations(self, report: Optional[GuardrailReport]) -> bool:
        """Check if report has violations that should trigger architect."""
        if not report:
            return False
        architect_checks = {"file-size", "complexity", "circular-imports"}
        return any(v.check_id in architect_checks for v in report.violations)
    
    def _has_tester_violations(self, report: Optional[GuardrailReport]) -> bool:
        """Check if report has violations that should trigger tester."""
        if not report:
            return False
        tester_checks = {"test-coverage", "dead-code"}
        return any(v.check_id in tester_checks for v in report.violations)
    
    def _has_integrator_violations(self, report: Optional[GuardrailReport]) -> bool:
        """Check if report has violations that should trigger integrator."""
        if not report:
            return False
        integrator_checks = {"secrets", "documentation-drift", "todo"}
        return any(v.check_id in integrator_checks for v in report.violations)
