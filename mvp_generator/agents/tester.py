"""Tester agent responsible for writing unit tests for the generated MVP."""

import logging
from typing import Dict, Optional

from engine.state import MathResult
from mvp_generator.agents.base_agent import BaseSwarmAgent

logger = logging.getLogger(__name__)


class TesterAgent(BaseSwarmAgent):
    """Generates a pytest suite based on the math logic and expected results."""

    def __init__(self, model: str = "gemini-1.5-pro") -> None:
        super().__init__(
            name="Tester",
            role="Responsible for writing comprehensive unit tests for the project. "
                 "You write pytest test cases that verify correctness and catch edge cases.",
            model=model
        )

    def write_tests(
        self, 
        math_result: MathResult, 
        implemented_code: Dict[str, str],
        violation_feedback: Optional[str] = None
    ) -> str:
        """Writes pytest cases ensuring mathematical and engineering correctness."""
        
        # Extract solver code for context
        solver_code = ""
        for path, code in implemented_code.items():
            if "solver" in path or "main" in path:
                solver_code += f"\n# {path}\n{code}\n"
        
        prompt = f"""
Math Problem Result:
Expected Answer: {math_result.final_answer}
Logic Steps: {[s.title for s in math_result.steps]}

Solver Implementation:
```python
{solver_code[:2000]}  # Truncated for context
```

Write a comprehensive `tests/test_solver.py` file using pytest.

REQUIREMENTS:
- Test the core solver function with the expected answer
- Include edge case tests (empty input, invalid input, boundary values)
- Include numerical stability tests if applicable
- Use pytest.approx for floating point comparisons
- ALL test functions must have type hints
- Follow HelicOps standards: no bare except, no print statements
- Aim for high test coverage

The test should verify that the implementation produces: {math_result.final_answer}

Return ONLY the Python test code.
"""
        
        if violation_feedback:
            prompt += f"""

Additionally, fix these violations in your test code:
{violation_feedback}
"""

        response = self._generate(prompt)
        return self._strip_markdown_code(response)
