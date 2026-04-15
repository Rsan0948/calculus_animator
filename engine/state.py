"""Immutable pipeline state definitions.

Strict Pydantic v2 models govern how data moves between:
  - Ingestion & Formalization
  - Unified Math Engine
  - Explainer
  - MVP Generator
  - Guardrail Critic
  - Run persistence and resume state
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


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
    domain: str = "ℝ"
    type_hint: str = "Any"


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


class ExtractionReport(BaseModel):
    """Diagnostic report for the PDF extraction stage."""

    extractor_used: str
    fallback_attempts: list[str] = Field(default_factory=list)
    raw_character_count: int = 0
    normalized_character_count: int = 0
    line_count: int = 0
    page_count: int | None = None
    scanned_pdf_suspected: bool = False
    warnings: list[str] = Field(default_factory=list)
    extractor_metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    """Normalized extraction output and its diagnostics."""

    text: str
    report: ExtractionReport


class ChunkRecord(BaseModel):
    """One persisted chunk in the deterministic chunk manifest."""

    index: int
    content: str
    character_count: int
    preview: str


class ChunkReport(BaseModel):
    """Chunk manifest and aggregate chunking diagnostics."""

    total_chunks: int
    total_characters: int
    min_chunk_size: int
    max_chunk_size: int
    average_chunk_size: float
    dropped_empty_chunks: int = 0
    warnings: list[str] = Field(default_factory=list)
    chunks: list[ChunkRecord] = Field(default_factory=list)

    def chunk_texts(self) -> list[str]:
        """Return the ordered chunk payloads for downstream formalization."""
        return [chunk.content for chunk in self.chunks]


class FormalizationAttemptReport(BaseModel):
    """One formalization pipeline attempt or validation pass."""

    phase: Literal["extract", "repair", "validate"]
    success: bool = False
    notes: list[str] = Field(default_factory=list)
    raw_response_preview: str | None = None


class FormalizationReport(BaseModel):
    """Diagnostics for the strict multi-pass formalization flow."""

    accepted: bool = False
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    assumptions: list[str] = Field(default_factory=list)
    ambiguity_notes: list[str] = Field(default_factory=list)
    dropped_fields: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    refusal_reason: str | None = None
    attempts: list[FormalizationAttemptReport] = Field(default_factory=list)
    selected_chunk_count: int = 0
    objective_present: bool = False
    domain_tag_count: int = 0
    model: str = ""


class FormalizedProblem(BaseModel):
    """Structured DSL representing a problem extracted from a paper."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    source_document: SourceDocument = Field(default_factory=SourceDocument)
    extracted_at: datetime = Field(default_factory=utc_now)

    title: str = ""
    domain_tags: list[str] = Field(default_factory=list)
    objective: str = ""
    variables: list[Variable] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    theoretical_framework: str = ""
    expected_output: ExpectedOutput = Field(default_factory=lambda: ExpectedOutput(kind="symbolic_expression"))

    source_chunks: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def summary(self) -> str:
        chunks = [
            f"Title: {self.title}",
            f"Domains: {', '.join(self.domain_tags) or 'unknown'}",
            f"Objective: {self.objective}",
            f"Variables: {[variable.symbol for variable in self.variables]}",
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
    final_answer: str | None = None
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
    timestamp: datetime = Field(default_factory=utc_now)
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


class MVPAttempt(BaseModel):
    """A single orchestrator attempt captured for later inspection."""

    attempt_number: int
    generated_files: list[str] = Field(default_factory=list)
    overall_pass: bool = False
    math_validation_pass: bool = False
    violation_count: int = 0
    violation_check_ids: list[str] = Field(default_factory=list)


class MVPOutput(BaseModel):
    """The final package produced by the MVP Generator."""

    problem_id: str
    generated_at: datetime = Field(default_factory=utc_now)
    root_directory: str
    files: list[GeneratedFile] = Field(default_factory=list)
    guardrail_report: GuardrailReport | None = None
    attempt_history: list[MVPAttempt] = Field(default_factory=list)
    install_command: str = "pip install -e ."
    run_command: str = "python main.py"


RunStatus = Literal["pending", "running", "completed", "failed"]
RunStageStatus = Literal["pending", "running", "completed", "failed", "invalidated", "skipped"]
RunStageName = Literal[
    "validate_input",
    "extract",
    "chunk",
    "formalize",
    "route",
    "solve",
    "generate_mvp",
]

RUN_STAGE_SEQUENCE: tuple[RunStageName, ...] = (
    "validate_input",
    "extract",
    "chunk",
    "formalize",
    "route",
    "solve",
    "generate_mvp",
)
RUN_STAGE_ORDER: dict[str, int] = {
    stage_name: index for index, stage_name in enumerate(RUN_STAGE_SEQUENCE)
}


class RunArtifactRef(BaseModel):
    """A persisted artifact produced during one run stage."""

    artifact_type: str
    path: str
    stage_name: RunStageName
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    content_hash: str | None = None


class RunStageRecord(BaseModel):
    """Execution state for one stage within a persisted run."""

    run_id: str
    stage_name: RunStageName
    status: RunStageStatus = "pending"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: dict[str, Any] | str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[RunArtifactRef] = Field(default_factory=list)


class RunRecord(BaseModel):
    """Top-level persisted run record for the active CLI workflow."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    problem_id: str | None = None
    source_path: str
    source_type: Literal["pdf"] = "pdf"
    source_fingerprint: str
    command_name: str = "run"
    status: RunStatus = "pending"
    current_stage: RunStageName | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_error: dict[str, Any] | str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
