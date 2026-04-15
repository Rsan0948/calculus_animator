"""Immutable pipeline state definitions.

Strict Pydantic v2 models govern how data moves between:
  - Ingestion & Formalization
  - Unified Math Engine
  - Explainer
  - MVP Generator
  - Guardrail Critic
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class SourceDocument(BaseModel):
    """Metadata about the ingested research paper."""

    format: Literal["pdf", "arxiv", "latex", "markdown", "unknown"] = "unknown"
    uri: str | None = None
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    extracted_text: str | None = None


class Variable(BaseModel):
    """A symbolic variable extracted from a problem statement."""

    symbol: str
    description: str = ""
    domain: str = "ℝ"  # e.g., ℝ, ℤ+, Boolean, ℕ
    type_hint: str = "Any"  # Suggested Python type


class Constraint(BaseModel):
    """A constraint on the problem space."""

    kind: Literal["equation", "inequality", "logical", "set_membership", "other"] = "equation"
    expression_latex: str
    description: str = ""


class ExpectedOutput(BaseModel):
    """What the solver is expected to produce."""

    kind: Literal[
        "symbolic_expression",
        "numerical_value",
        "algorithm",
        "proof",
        "visualization",
    ]
    description: str = ""


class FormalizedProblem(BaseModel) :
    """Structured DSL representing a problem extracted from a paper."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    source_document: SourceDocument = Field(default_factory=SourceDocument)
    extracted_at: datetime = Field(default_factory=datetime.utcnow)

    title: str = ""
    domain_tags: list[str] = Field(default_factory=list)
    objective: str = ""
    variables: list[Variable] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    theoretical_framework: str = ""
    expected_output: ExpectedOutput = Field(default_factory=lambda: ExpectedOutput(kind="symbolic_expression"))

    # Raw context for RAG / debugging
    source_chunks: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def summary(self) -> str:
        chunks = [
            f"Title: {self.title}",
            f"Domains: {', '.join(self.domain_tags) or 'unknown'}",
            f"Objective: {self.objective}",
            f"Variables: {[v.symbol for v in self.variables]}",
            f"Expected output: {self.expected_output.kind}",
        ]
        return "\n".join(chunks)


class VisualHint(BaseModel):
    """Hints for the visual generator about how to render a step."""

    kind: Literal[
        "graph",
        "matrix",
        "network",
        "tree",
        "table",
        "highlight",
        "none",
    ] = "none"
    payload: dict[str, Any] = Field(default_factory=dict)


class MathStep(BaseModel):
    """A single step in a mathematical solution."""

    step_number: int
    title: str = ""
    description: str = ""
    before_latex: str | None = None
    after_latex: str | None = None
    rule_applied: str | None = None
    visual_hints: list[VisualHint] = Field(default_factory=list)


class MathResult(BaseModel):
    """The output of the Unified Math Engine."""

    problem_id: str
    plugin_used: str
    success: bool = True
    final_answer: str | None = None  # LaTeX or string representation
    steps: list[MathStep] = Field(default_factory=list)
    graph_data: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    failure_reason: dict[str, Any] | str | None = None


class Violation(BaseModel):
    """A single guardrail or policy violation from HelicOps."""

    check_id: str
    file_path: str | None = None
    line_number: int | None = None
    message: str
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    fix_suggestion: str | None = None


class GuardrailReport(BaseModel):
    """Summary of the quality audit for a generated MVP, powered by HelicOps."""

    target_path: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    overall_pass: bool = False
    violations: list[Violation] = Field(default_factory=list)
    test_coverage: float = 0.0
    math_validation_pass: bool = False
    audit_summary: dict[str, Any] = Field(default_factory=dict)


class GeneratedFile(BaseModel):
    """A file generated as part of an MVP."""

    relative_path: str
    content: str
    purpose: str = ""


class MVPOutput(BaseModel):
    """The final package produced by the MVP Generator."""

    problem_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    root_directory: str
    files: list[GeneratedFile] = Field(default_factory=list)
    guardrail_report: GuardrailReport | None = None
    install_command: str = "pip install -e ."
    run_command: str = "python main.py"
