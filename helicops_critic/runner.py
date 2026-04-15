"""HelicOps Critic: interfaces with HelicOps to audit generated MVPs."""

import logging
from pathlib import Path
from typing import Optional

from engine.state import GuardrailReport, Violation
from helicops_critic.integration import HelicOpsIntegration
from helicops_critic.math_validator import MathValidator

logger = logging.getLogger(__name__)


class HelicOpsCritic:
    """Critic that uses HelicOps to enforce engineering and security standards.
    
    Uses the native Python integration (helicops-py package) for efficient
    guardrail execution.
    """

    def __init__(
        self, 
        config_path: Optional[Path] = None,
        allow_mock: bool = False
    ) -> None:
        """Initialize the critic.
        
        Args:
            config_path: Path to HelicOps config.
            allow_mock: If False, raises error if HelicOps unavailable.
                       If True, uses mock mode (always passes).
        """
        self.helicops = HelicOpsIntegration(
            config_path=config_path,
            allow_mock=allow_mock
        )
        self.math_validator = MathValidator()
        
        # Log guardrail info
        info = self.helicops.get_guardrail_info()
        if info.get("available"):
            logger.info("HelicOpsCritic initialized with %d guardrails", info["count"])
        elif allow_mock:
            logger.warning("HelicOpsCritic running in mock mode (helicops unavailable)")
        else:
            logger.error("HelicOps not available and allow_mock=False")
            raise RuntimeError("HelicOps not available. Set allow_mock=True for development.")

    def audit(self, workspace_path: Path, math_result: None=None) -> GuardrailReport:
        """Run the full critic audit on the workspace.
        
        Args:
            workspace_path: Path to the generated MVP
            math_result: Optional MathResult for validation
            
        Returns:
            GuardrailReport with all violations and status
        """
        logger.info("Critic: Auditing workspace %s...", workspace_path)
        
        # 1. Run HelicOps guardrails
        report = self.helicops.audit_workspace(workspace_path)
        
        # 2. Run math validation if we have a reference result
        if math_result:
            math_pass = self.math_validator.validate(workspace_path, math_result)
            report.math_validation_pass = math_pass
            # If math validation fails, overall is fail
            if not math_pass and report.overall_pass:
                report.overall_pass = False
        
        logger.info("Critic: Audit complete. Pass=%s, Violations=%d", 
                   report.overall_pass, len(report.violations))
        
        return report
    
    def get_violations_by_agent(self, report: GuardrailReport) -> dict:
        """Map violations to the agent that should fix them.
        
        Returns:
            Dict mapping agent names to lists of violations they should fix.
        """
        mapping = {
            "architect": ["file-size", "complexity", "circular-imports"],
            "algorithm": ["type-hints", "unsafe-execution", "agent-credentials", 
                         "silent-exceptions", "absolute-paths", "print-statements"],
            "tester": ["test-coverage", "dead-code"],
            "integrator": ["secrets", "documentation-drift", "todo"]
        }
        
        result = {agent: [] for agent in mapping}
        
        for violation in report.violations:
            check_id = violation.check_id
            assigned = False
            
            for agent, patterns in mapping.items():
                if any(pattern in check_id.lower() for pattern in patterns):
                    result[agent].append(violation)
                    assigned = True
                    break
            
            if not assigned:
                # Default to algorithm for unknown violations
                result["algorithm"].append(violation)
        
        return result
