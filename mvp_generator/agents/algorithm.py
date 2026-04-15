"""Algorithm agent responsible for implementing the core mathematical logic."""

import logging
from typing import Optional

from engine.state import MathResult
from mvp_generator.agents.base_agent import BaseSwarmAgent

logger = logging.getLogger(__name__)


class AlgorithmAgent(BaseSwarmAgent):
    """Translates math logic into high-quality Python code."""

    def __init__(self, model: str = "gemini-1.5-pro") -> None:
        super().__init__(
            name="Algorithm",
            role="Responsible for implementing the core mathematical logic in Python. "
                 "You write clean, typed, well-documented code that correctly implements "
                 "the mathematical solution. You NEVER use absolute paths, ALWAYS use "
                 "type hints, and NEVER use bare except blocks.",
            model=model
        )

    def implement(
        self, 
        math_result: MathResult, 
        file_path: str,
        purpose: str,
        existing_code: Optional[str] = None,
        violation_feedback: Optional[str] = None
    ) -> str:
        """Implements the code for a specific file based on the math result.
        
        Args:
            math_result: The solved math problem
            file_path: Target file path
            purpose: Description of what this file should do
            existing_code: Previous implementation (for retry/fix scenarios)
            violation_feedback: HelicOps violation feedback to address
        """
        
        # Build prompt based on whether this is a fix or new implementation
        if existing_code and violation_feedback:
            prompt = self._build_fix_prompt(
                math_result, file_path, purpose, 
                existing_code, violation_feedback
            )
        else:
            prompt = self._build_implement_prompt(math_result, file_path, purpose)
        
        response = self._generate(prompt)
        return self._strip_markdown_code(response)
    
    def _build_implement_prompt(
        self, 
        math_result: MathResult, 
        file_path: str,
        purpose: str
    ) -> str:
        """Build prompt for new implementation."""
        return f"""
Math Problem Result:
Answer: {math_result.final_answer}
Step-by-Step Logic:
{[f"{s.step_number}. {s.title}: {s.description}" for s in math_result.steps]}

Target File: {file_path}
Purpose: {purpose}

Write the Python implementation for this file.

REQUIREMENTS (HelicOps compliant):
- Use type hints on ALL functions and variables
- Include comprehensive docstrings
- Follow PEP 8
- NEVER use absolute paths (no /Users/, /home/, C:\\)
- NEVER use bare except blocks - always catch specific exceptions
- Use logging instead of print()
- Ensure the code correctly implements the mathematical steps
- Add proper error handling

Return ONLY the Python code, no markdown blocks.
"""
    
    def _build_fix_prompt(
        self,
        math_result: MathResult,
        file_path: str,
        purpose: str,
        existing_code: str,
        violation_feedback: str
    ) -> str:
        """Build prompt for fixing violations."""
        return f"""
You are fixing code that failed HelicOps guardrails.

Current Implementation ({file_path}):
```python
{existing_code}
```

{violation_feedback}

Math Problem Context:
Answer: {math_result.final_answer}
Steps: {[s.title for s in math_result.steps]}

INSTRUCTIONS:
1. Fix ALL the violations listed above
2. Keep the mathematical logic correct
3. Maintain the same functionality
4. Return the complete fixed file

REQUIREMENTS:
- Use type hints on ALL functions
- NEVER use bare except blocks - use `except SpecificError:`
- NEVER use absolute paths
- Use logging, not print
- Include proper docstrings

Return ONLY the fixed Python code.
"""
