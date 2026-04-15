"""Math Validator: verifies generated code output against math oracle."""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

import sympy

from engine.state import MathResult

logger = logging.getLogger(__name__)


class MathValidationError(Exception):
    """Raised when math validation fails."""
    pass


class MathValidator:
    """Validator that runs generated code and compares output to oracle answer."""

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def _mathematically_equivalent(self, generated: str, expected: str) -> bool:
        """Check if two mathematical expressions are equivalent using SymPy.
        
        Args:
            generated: Generated answer string.
            expected: Expected answer string.
            
        Returns:
            True if expressions are mathematically equivalent.
        """
        # Handle simple string match first (fast path)
        if expected in generated or generated in expected:
            return True
        
        # Try symbolic comparison
        try:
            gen_expr = sympy.sympify(generated)
            exp_expr = sympy.sympify(expected)
            
            # Check if difference simplifies to zero
            diff = sympy.simplify(gen_expr - exp_expr)
            if diff == 0:
                return True
            
            # Check numerical equivalence for complex expressions
            try:
                # Evaluate at a few test points
                import random
                for _ in range(3):
                    # Substitute random values for free symbols
                    subs = {s: random.uniform(0.1, 10.0) for s in gen_expr.free_symbols}
                    gen_val = float(gen_expr.evalf(subs=subs))
                    exp_val = float(exp_expr.evalf(subs=subs))
                    
                    # Allow small numerical tolerance
                    if abs(gen_val - exp_val) > 1e-6:
                        return False
                return True
            except Exception:
                pass
            
        except (sympy.SympifyError, TypeError, ValueError):
            # Not valid sympy expressions, fall back to string comparison
            pass
        
        return False

    def validate(self, workspace_path: Path, math_result: MathResult) -> bool:
        """Runs the generated main.py and checks if output matches expected answer.
        
        Args:
            workspace_path: Path to the generated MVP directory.
            math_result: The expected math result.
            
        Returns:
            True if validation passes, False otherwise.
        """
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
                timeout=self.timeout
            )
            
            output = result.stdout + result.stderr
            expected = str(math_result.final_answer)
            
            # Try to extract answer from output (look for common patterns)
            generated_answer = self._extract_answer(output)
            
            if generated_answer:
                # Use mathematical equivalence checking
                if self._mathematically_equivalent(generated_answer, expected):
                    logger.info("Validator: SUCCESS! Output matches oracle (%s == %s)", 
                               generated_answer, expected)
                    return True
                else:
                    logger.warning("Validator: FAILED. Generated '%s' != expected '%s'",
                                 generated_answer, expected)
                    return False
            else:
                # Fall back to simple string containment
                if expected in output:
                    logger.info("Validator: SUCCESS! Expected value found in output.")
                    return True
                else:
                    logger.warning("Validator: FAILED. Expected '%s' not found in output.", expected)
                    return False
                
        except subprocess.TimeoutExpired:
            logger.error("Validator: TIMEOUT after %d seconds", self.timeout)
            return False
        except Exception as e:
            logger.error("Validator error: %s", e)
            return False
    
    def _extract_answer(self, output: str) -> Optional[str]:
        """Try to extract a mathematical answer from program output.
        
        Looks for patterns like:
        - "Answer: <value>"
        - "Result: <value>"
        - "= <value>"
        - Last line if it looks like math
        
        Args:
            output: Program stdout/stderr.
            
        Returns:
            Extracted answer or None.
        """
        lines = output.strip().split('\n')
        
        # Look for explicit answer patterns
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
                
            # Check for "Answer: X" or "Result: X" patterns
            for prefix in ["answer:", "result:", "solution:", "="]:
                if prefix in line.lower():
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        return parts[1].strip()
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        return parts[1].strip()
        
        # Last resort: try the last non-empty line
        for line in reversed(lines):
            line = line.strip()
            if line:
                # Check if it looks like a mathematical expression
                # (contains numbers, operators, or common math symbols)
                if any(c in line for c in "0123456789+-*/=^()x"):
                    return line
        
        return None
