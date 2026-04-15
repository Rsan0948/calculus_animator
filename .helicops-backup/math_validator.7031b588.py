"""Math Validator: verifies generated code output against math oracle."""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

from engine.state import MathResult

logger = logging.getLogger(__name__)


class MathValidator:
    """Validator that runs generated code and compares output to oracle answer."""

    def validate(self, workspace_path: Path, math_result: MathResult) -> bool:
        """Runs the generated main.py and checks if the output contains the final answer."""
        
        main_py = workspace_path / "main.py"
        if not main_py.exists():
            main_py = workspace_path / "src/main.py"
            
        if not main_py.exists():
            logger.error("Validator: main.py not found in %s", workspace_path)
            return False

        logger.info("Validator: Running generated code to verify math...")
        
        try:
            # Run the generated script
            result = subprocess.run(
                [sys.executable, str(main_py)],
                capture_output=True,
                text=True,
                cwd=workspace_path,
                timeout=30
            )
            
            output = result.stdout + result.stderr
            expected = str(math_result.final_answer)
            
            # Simple check: is the expected answer in the output?
            # (In a more robust version, we'd parse the output properly)
            if expected in output:
                logger.info("Validator: SUCCESS! Output matches oracle.")
                return True
            else:
                logger.warning("Validator: FAILED. Expected '%s' but not found in output.", expected)
                return False
                
        except Exception as e:
            logger.error("Validator error: %s", e)
            return False
