"""Integrator agent responsible for finalizing the MVP package."""

import json
import logging
from typing import Dict, Optional

from engine.state import MathResult
from mvp_generator.agents.base_agent import BaseSwarmAgent

logger = logging.getLogger(__name__)


class IntegratorAgent(BaseSwarmAgent):
    """Wires modules together, writes README, and project configs."""

    def __init__(self, model: str = "gemini-1.5-pro"):
        super().__init__(
            name="Integrator",
            role="Responsible for final project assembly and documentation. "
                 "You create pyproject.toml, README.md, and other project files "
                 "that make the package installable and usable.",
            model=model
        )

    def finalize(
        self, 
        math_result: MathResult, 
        implemented_code: Dict[str, str],
        violation_feedback: Optional[str] = None
    ) -> Dict[str, str]:
        """Generates the remaining project files (README, pyproject.toml)."""
        
        files_list = list(implemented_code.keys())
        
        prompt = f"""
Math Problem Result:
Expected Answer: {math_result.final_answer}

Implemented Files:
{files_list}

Write the remaining boilerplate files for a modern Python project.
Return a JSON object where keys are file paths and values are the full content.

REQUIRED FILES:
- pyproject.toml (with [build-system], [project], [project.optional-dependencies] dev)
- README.md (comprehensive with installation, usage, example)
- .gitignore (Python standard)
- src/__init__.py (if src/ directory is used)

REQUIREMENTS:
- README must be comprehensive with usage examples
- pyproject.toml must be valid and installable
- NO hardcoded absolute paths
- Include proper package metadata
- Include dev dependencies: pytest, ruff, mypy

Return ONLY valid JSON in this format:
{{
  "pyproject.toml": "content here",
  "README.md": "content here",
  ".gitignore": "content here"
}}
"""
        
        if violation_feedback:
            prompt += f"""

Fix these violations in your output:
{violation_feedback}
"""

        response = self._generate(prompt)
        
        try:
            clean_json = response.strip().strip("```json").strip("```").strip()
            return json.loads(clean_json)
        except Exception as e:
            logger.error("Integrator failed to parse JSON: %s", e)
            # Return minimal valid structure
            return {
                "README.md": f"# Research MVP\n\nGenerated solution for: {math_result.final_answer}",
                "pyproject.toml": """[build-system]
requires = ["setuptools>=61", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "research-mvp"
version = "0.1.0"
description = "Generated MVP from research engine"
requires-python = ">=3.10"

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.4", "mypy>=1.0"]
""",
                ".gitignore": "__pycache__/\n*.pyc\n.venv/\ndist/\n*.egg-info/\n.pytest_cache/\n"
            }
