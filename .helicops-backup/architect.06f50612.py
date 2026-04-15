"""Architect agent responsible for designing the MVP project structure."""

import json
import logging
from typing import Dict, Optional

from engine.state import MathResult
from mvp_generator.agents.base_agent import BaseSwarmAgent

logger = logging.getLogger(__name__)


class ArchitectAgent(BaseSwarmAgent):
    """Designs the module structure and defines interfaces for the MVP."""

    def __init__(self, model: str = "gemini-1.5-pro"):
        super().__init__(
            name="Architect",
            role="Responsible for designing the file and module structure of the Python project. "
                 "You create clean, modular designs that follow best practices and will pass "
                 "HelicOps guardrails (reasonable file sizes, no circular imports).",
            model=model
        )

    def design(
        self, 
        math_result: MathResult,
        violation_feedback: Optional[str] = None
    ) -> Dict[str, str]:
        """Creates a manifest of files and their purposes based on the math result."""
        
        prompt = f"""
Math Problem Result:
Answer: {math_result.final_answer}
Logic Steps: {[s.title for s in math_result.steps]}

Design a production-ready Python project that implements a solver for this problem.

REQUIREMENTS:
- Output a JSON manifest where keys are file paths and values are brief descriptions
- Keep files under 300 lines (HelicOps file-size guardrail)
- Use modular design - split logic appropriately
- Include:
  - pyproject.toml
  - README.md
  - src/solver.py (core logic)
  - src/main.py (CLI entry point)
  - tests/test_solver.py (pytest suite)
  - src/__init__.py

- Use src/ layout (modern Python packaging)
- No circular imports
- Clean separation of concerns

Return ONLY JSON in this format:
{{
  "pyproject.toml": "Project configuration",
  "src/__init__.py": "Package init",
  "src/solver.py": "Core mathematical solver",
  "src/main.py": "CLI entry point",
  "tests/test_solver.py": "Pytest suite",
  "README.md": "Documentation"
}}
"""
        
        if violation_feedback:
            prompt += f"""

IMPORTANT - Fix these architectural issues:
{violation_feedback}
"""

        response = self._generate(prompt)
        
        try:
            clean_json = response.strip().strip("```json").strip("```").strip()
            return json.loads(clean_json)
        except Exception as e:
            logger.error("Architect failed to parse design JSON: %s", e)
            # Fallback structure
            return {
                "pyproject.toml": "Project configuration",
                "README.md": "Project documentation",
                "src/__init__.py": "Package initialization",
                "src/solver.py": "Core mathematical logic",
                "src/main.py": "Command-line interface",
                "tests/test_solver.py": "Pytest suite"
            }
