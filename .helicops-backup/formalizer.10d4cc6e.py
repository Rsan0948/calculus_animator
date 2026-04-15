"""Formalizes extracted research paper chunks into a structured DSL."""

import json
import logging
import re
from typing import List, Optional

from engine.state import (
    Constraint,
    ExpectedOutput,
    FormalizedProblem,
    SourceDocument,
    Variable,
)
from ai_backend.providers.router import _call_gemini_cli

logger = logging.getLogger(__name__)


class Formalizer:
    """Uses an LLM to extract a structured math problem from research text."""

    def __init__(self, model: str = "gemini-1.5-pro"):
        self.model = model

    def formalize(
        self, 
        chunks: List[str], 
        source_doc: Optional[SourceDocument] = None
    ) -> FormalizedProblem:
        """Sends chunks to the LLM and parses the structured output."""
        
        # Combine chunks for context (could be smarter with RAG in a full implementation)
        context = "\n---\n".join(chunks[:5])  # Limit to first few chunks for now
        
        system_prompt = (
            "You are a mathematical formalization expert. Your goal is to extract "
            "a precise, structured mathematical problem from a research paper excerpt. "
            "Output MUST be valid JSON matching the requested schema."
        )
        
        prompt = f"""
Research Paper Excerpt:
{context}

Based on the excerpt above, identify the core mathematical or computational problem.
Extract it into the following JSON format:
{{
  "title": "Problem Title",
  "domain_tags": ["tag1", "tag2"],
  "objective": "The main goal in LaTeX format if applicable",
  "variables": [
    {{"symbol": "x", "description": "variable description", "domain": "ℝ", "type_hint": "float"}}
  ],
  "constraints": [
    {{"kind": "equation", "expression_latex": "f(x) = 0", "description": "const description"}}
  ],
  "theoretical_framework": "Relevant theorems or lemmas",
  "expected_output": {{
    "kind": "symbolic_expression",
    "description": "What the final answer should look like"
  }}
}}

Ensure all math is in LaTeX. Be as precise as possible.
If the paper describes an unsolved problem, formalize the challenge.
"""

        try:
            response_text = _call_gemini_cli(prompt, model=self.model, system=system_prompt)
            
            # Extract JSON from response (handling potential markdown formatting)
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                data = json.loads(response_text)
                
            # Convert dict to Pydantic models
            return FormalizedProblem(
                source_document=source_doc or SourceDocument(),
                title=data.get("title", ""),
                domain_tags=data.get("domain_tags", []),
                objective=data.get("objective", ""),
                variables=[Variable(**v) for v in data.get("variables", [])],
                constraints=[Constraint(**c) for c in data.get("constraints", [])],
                theoretical_framework=data.get("theoretical_framework", ""),
                expected_output=ExpectedOutput(**data.get("expected_output", {"kind": "symbolic_expression"})),
                source_chunks=chunks[:5]
            )
        except Exception as e:
            logger.error("Formalization failed: %s", e)
            # Return a minimal problem on failure
            return FormalizedProblem(
                source_document=source_doc or SourceDocument(),
                objective="Formalization failed. See logs.",
                source_chunks=chunks[:5]
            )
