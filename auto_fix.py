#!/usr/bin/env python3
"""Auto-fix HelicOps violations using the fix engine."""

import logging
import sys
from pathlib import Path

# Add HelicOps to path
sys.path.insert(0, str(Path("~/Desktop/HelicOps/packages/py").expanduser()))

from helicops_py.fixers.engine import FixEngine
from helicops_py.runner import find_python_files

def main() -> None:
    project_root = Path(".").resolve()
    
    # Find Python files
    py_files = find_python_files(project_root)
    
    # Create fix engine
    engine = FixEngine()
    
    print(f"🔧 Auto-fixing {len(py_files)} Python files...")
    print("=" * 50)
    
    total_fixed = 0
    files_changed = 0
    
    for filepath in py_files:
        # Skip certain paths
        if any(skip in str(filepath) for skip in [
            "calculus_animator/",
            ".venv/", "__pycache__/", ".git/",
        ]):
            continue
        
        results = engine.fix_file(str(filepath), dry_run=False, project_root=project_root, force=True)
        
        if results:
            print(f"\n📄 {filepath.relative_to(project_root)}")
            for result in results:
                print(f"   ✅ Fixed: {result.guardrail_id}")
                for change in result.changes:
                    print(f"      Lines {change.start_line}-{change.end_line}: {change.description}")
            total_fixed += len(results)
            files_changed += 1
    
    print("\n" + "=" * 50)
    print(f"🔧 Total fixes applied: {total_fixed} in {files_changed} files")
    
    if total_fixed > 0:
        print("\n⚠️  Please review the changes before committing!")
        print("   git diff to see what changed")

if __name__ == "__main__":
    main()
