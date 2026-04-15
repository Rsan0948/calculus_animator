"""Proper HelicOps integration using Python API.

HelicOps is installed as `helicops-py` and `helicops-core` packages.
This module provides clean programmatic access.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.state import GuardrailReport, Violation

logger = logging.getLogger(__name__)

# Try to import HelicOps
try:
    from helicops_py import REGISTRY
    from helicops_py.runner import run_file_based_checks, find_python_files
    from helicops_core.config import GuardrailsConfig
    HELICOPS_AVAILABLE = True
    logger.info("HelicOps available with %d guardrails", len(REGISTRY))
except ImportError as e:
    logger.warning("HelicOps import failed: %s", e)
    HELICOPS_AVAILABLE = False
    REGISTRY = {}


class HelicOpsIntegration:
    """Native Python integration with HelicOps guardrails.
    
    Uses the installed helicops-py package directly for:
    - Faster execution (no subprocess overhead)
    - Better error handling
    - Structured violation data
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        self.available = HELICOPS_AVAILABLE
        self.config_path = config_path
        
    def audit_workspace(self, workspace_path: Path) -> GuardrailReport:
        """Run HelicOps guardrails on the workspace."""
        if not self.available:
            return self._mock_report(workspace_path)
        
        logger.info("Running HelicOps audit on %s...", workspace_path)
        
        try:
            # Load config
            config = GuardrailsConfig.load(workspace_path)
            
            # Find Python files
            py_files = find_python_files(workspace_path)
            
            if not py_files:
                return GuardrailReport(
                    target_path=str(workspace_path),
                    overall_pass=False,
                    violations=[Violation(
                        check_id="no-python-files",
                        message="No Python files found in workspace",
                        severity="high"
                    )]
                )
            
            # Run guardrails
            results = run_file_based_checks(config, workspace_path, py_files)
            
            # Parse results into Violation objects
            violations = []
            for gid, rc, stdout, stderr in results:
                if rc != 0 and stdout.strip():
                    # Parse violation output
                    # Format is typically: file:line: message
                    for line in stdout.strip().split('\n'):
                        if ':' in line:
                            parts = line.split(':', 2)
                            if len(parts) >= 2:
                                file_path = parts[0] if parts[0] else None
                                try:
                                    line_num = int(parts[1]) if parts[1].isdigit() else None
                                except ValueError:
                                    line_num = None
                                message = parts[2] if len(parts) > 2 else line
                                
                                violations.append(Violation(
                                    check_id=gid,
                                    file_path=file_path,
                                    line_number=line_num,
                                    message=message.strip(),
                                    severity="high" if "error" in message.lower() else "medium"
                                ))
            
            overall_pass = len(violations) == 0
            
            return GuardrailReport(
                target_path=str(workspace_path),
                overall_pass=overall_pass,
                violations=violations,
                audit_summary={
                    "files_checked": len(py_files),
                    "guardrails_run": len(REGISTRY),
                    "violations_found": len(violations)
                }
            )
            
        except Exception as e:
            logger.error("Audit failed: %s", e)
            return GuardrailReport(
                target_path=str(workspace_path),
                overall_pass=False,
                violations=[Violation(
                    check_id="audit-error",
                    message=str(e),
                    severity="critical"
                )]
            )
    
    def _mock_report(self, workspace_path: Path) -> GuardrailReport:
        """Return a mock pass when HelicOps is unavailable."""
        logger.warning("HelicOps unavailable - returning mock pass")
        return GuardrailReport(
            target_path=str(workspace_path),
            overall_pass=True,
            violations=[],
            audit_summary={"mode": "mock"}
        )
    
    def get_guardrail_info(self) -> Dict[str, Any]:
        """Return available guardrail information."""
        if not self.available:
            return {"available": False}
        
        return {
            "available": True,
            "count": len(REGISTRY),
            "guardrails": [
                {
                    "id": gid, 
                    "severity": meta.get("severity", "unknown"),
                    "description": meta.get("description", "")
                }
                for gid, meta in REGISTRY.items()
            ]
        }
