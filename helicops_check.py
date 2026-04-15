import sys
from pathlib import Path
import logging
from helicops_critic.integration import HelicOpsIntegration

logging.basicConfig(level=logging.INFO)

def run_check():
    integration = HelicOpsIntegration()
    if not integration.available:
        print("❌ HelicOps not available")
        sys.exit(1)
        
    workspace_path = Path.cwd()
    print(f"🔍 Auditing workspace: {workspace_path}")
    report = integration.audit_workspace(workspace_path)
    
    print("\n" + "=" * 50)
    print("HELICOPS AUDIT REPORT")
    print("=" * 50)
    print(f"Overall Pass: {'✅' if report.overall_pass else '❌'}")
    print(f"Violations Found: {len(report.violations)}")
    
    if report.violations:
        print("\nViolations:")
        for v in report.violations:
            location = f"{v.file_path}:{v.line_number}" if v.file_path and v.line_number else v.file_path or "Unknown"
            print(f"  [{v.severity.upper()}] {v.check_id} at {location}")
            print(f"    {v.message}")
            
    if not report.overall_pass:
        sys.exit(1)

if __name__ == "__main__":
    run_check()
