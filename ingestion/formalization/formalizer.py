"""Formalizes extracted research paper chunks into a structured DSL."""

import json
import logging
from json import JSONDecodeError
from typing import Any, Optional

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from engine.state import (
    Constraint,
    ExpectedOutput,
    FormalizationAttemptReport,
    FormalizationReport,
    FormalizedProblem,
    SourceDocument,
    Variable,
)
from ingestion.formalization.llm_client import call_formalizer_llm
from ingestion.validators import ValidationError, validate_chunks

logger = logging.getLogger(__name__)

MAX_CONTEXT_CHUNKS = 5
MAX_RESPONSE_PREVIEW = 240
MIN_FORMALIZATION_CONFIDENCE = 0.7


class FormalizationError(Exception):
    """Raised when formalization fails after all retries."""


class Formalizer:
    """Uses an LLM to extract a structured math problem from research text."""

    def __init__(self, model: str = "gemini-1.5-pro") -> None:
        self.model = model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _call_llm_with_retry(self, prompt: str, system: str) -> str:
        """Call the LLM with retry logic."""
        try:
            return call_formalizer_llm(prompt=prompt, model=self.model, system=system)
        except Exception as exc:
            logger.warning("LLM call failed (will retry): %s", exc)
            raise

    def formalize(
        self,
        chunks: list[str],
        source_doc: Optional[SourceDocument] = None,
    ) -> FormalizedProblem:
        """Send chunks to the LLM and return a strictly validated problem."""
        problem, report = self.formalize_with_report(chunks, source_doc=source_doc)
        if problem is None:
            refusal_message = report.refusal_reason or "; ".join(report.validation_errors) or "Failed to formalize"
            raise FormalizationError(refusal_message)
        return problem

    def formalize_with_report(
        self,
        chunks: list[str],
        source_doc: Optional[SourceDocument] = None,
    ) -> tuple[FormalizedProblem | None, FormalizationReport]:
        """Run the strict multi-pass formalization flow and return diagnostics."""
        report = FormalizationReport(model=self.model)
        try:
            validate_chunks(chunks)
        except ValidationError as exc:
            message = f"Invalid chunks for formalization: {exc}"
            report.validation_errors.append(message)
            report.refusal_reason = message
            report.attempts.append(
                FormalizationAttemptReport(
                    phase="validate",
                    success=False,
                    notes=[message],
                )
            )
            return None, report

        context_chunks = [chunk.strip() for chunk in chunks if chunk.strip()][:MAX_CONTEXT_CHUNKS]
        report.selected_chunk_count = len(context_chunks)
        context = "\n---\n".join(context_chunks)
        system_prompt = (
            "You are a mathematical formalization expert. Your goal is to extract "
            "a precise, structured mathematical problem from a research paper excerpt. "
            "Output MUST be valid JSON matching the requested schema."
        )

        candidate_response: str
        try:
            candidate_response = self._call_llm_with_retry(
                self._build_candidate_prompt(context),
                system_prompt,
            )
            report.attempts.append(
                FormalizationAttemptReport(
                    phase="extract",
                    success=True,
                    raw_response_preview=self._preview(candidate_response),
                )
            )
        except Exception as exc:
            message = f"Candidate extraction failed: {exc}"
            report.validation_errors.append(message)
            report.refusal_reason = message
            report.attempts.append(
                FormalizationAttemptReport(
                    phase="extract",
                    success=False,
                    notes=[message],
                )
            )
            return None, report

        try:
            repaired_response = self._call_llm_with_retry(
                self._build_repair_prompt(candidate_response),
                system_prompt,
            )
            data = self._extract_json_payload(repaired_response)
            report.attempts.append(
                FormalizationAttemptReport(
                    phase="repair",
                    success=True,
                    raw_response_preview=self._preview(repaired_response),
                )
            )
        except Exception as exc:
            message = f"Repair step failed to produce valid JSON: {exc}"
            report.validation_errors.append(message)
            report.refusal_reason = message
            report.attempts.append(
                FormalizationAttemptReport(
                    phase="repair",
                    success=False,
                    notes=[message],
                    raw_response_preview=self._preview(candidate_response),
                )
            )
            report.attempts.append(
                FormalizationAttemptReport(
                    phase="validate",
                    success=False,
                    notes=[message],
                )
            )
            return None, report

        report.confidence = self._coerce_confidence(data.get("confidence"), 0.0)
        report.assumptions = self._normalize_string_list(data.get("assumptions"))
        report.ambiguity_notes = self._normalize_string_list(data.get("ambiguity_notes"))
        report.dropped_fields = self._normalize_string_list(data.get("dropped_fields"))
        report.refusal_reason = self._normalize_optional_string(data.get("refusal_reason"))
        report.objective_present = bool(str(data.get("objective") or "").strip())
        domain_tags = data.get("domain_tags") or []
        report.domain_tag_count = len(domain_tags) if isinstance(domain_tags, list) else 0

        validation_errors = self._validate_formalized_payload(data)
        problem: FormalizedProblem | None = None
        if not validation_errors:
            try:
                problem = self._build_problem(data, chunks, source_doc, report)
            except Exception as exc:
                validation_errors.append(str(exc))

        report.validation_errors = validation_errors
        report.accepted = problem is not None and not validation_errors
        if validation_errors:
            report.refusal_reason = report.refusal_reason or validation_errors[0]

        report.attempts.append(
            FormalizationAttemptReport(
                phase="validate",
                success=not validation_errors,
                notes=validation_errors,
            )
        )
        return problem, report

    def _extract_json_payload(self, response_text: str) -> dict[str, Any]:
        """Extract the first valid JSON object from an LLM response."""
        cleaned = response_text.strip()
        if not cleaned:
            raise FormalizationError("LLM returned an empty response")

        decoder = json.JSONDecoder()
        for start_index, character in enumerate(cleaned):
            if character != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(cleaned[start_index:])
            except JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload

        raise FormalizationError("LLM response did not contain valid JSON")

    def _build_problem(
        self,
        data: dict[str, Any],
        chunks: list[str],
        source_doc: Optional[SourceDocument],
        report: FormalizationReport,
    ) -> FormalizedProblem:
        """Convert decoded JSON into a validated problem model."""
        source = source_doc or SourceDocument()
        title = str(data.get("title") or source.title or "Untitled problem")
        objective = str(data.get("objective") or "").strip()
        domain_tags = [str(tag) for tag in data.get("domain_tags") or []]
        expected_output_data = data.get("expected_output") or {"kind": "symbolic_expression"}
        variables = [Variable(**variable) for variable in data.get("variables", [])]
        constraints = [Constraint(**constraint) for constraint in data.get("constraints", [])]

        return FormalizedProblem(
            source_document=source,
            title=title,
            domain_tags=domain_tags,
            objective=objective,
            variables=variables,
            constraints=constraints,
            theoretical_framework=str(data.get("theoretical_framework") or ""),
            expected_output=ExpectedOutput(**expected_output_data),
            source_chunks=[chunk for chunk in chunks[:MAX_CONTEXT_CHUNKS] if chunk.strip()],
            confidence=report.confidence,
            metadata={
                "formalization_assumptions": report.assumptions,
                "formalization_ambiguity_notes": report.ambiguity_notes,
                "formalization_model": self.model,
            },
        )

    def _build_candidate_prompt(self, context: str) -> str:
        schema = self._schema_block()
        return f"""
Research Paper Excerpt:
{context}

Identify the core mathematical or computational problem in the excerpt.
Produce a best-effort JSON draft with this schema:
{schema}

Rules:
- Fill every required field you can infer.
- If the excerpt is ambiguous, list the ambiguity in `ambiguity_notes`.
- If the excerpt does not contain enough information for a reliable problem statement, set `refusal_reason`.
- Confidence must be a number between 0 and 1.
- Keep the output as JSON only.
"""

    def _build_repair_prompt(self, candidate_response: str) -> str:
        schema = self._schema_block()
        return f"""
You previously produced this candidate formalization:
{candidate_response}

Rewrite it into valid JSON that strictly matches this schema:
{schema}

Rules:
- Preserve uncertainty explicitly in `ambiguity_notes`, `assumptions`, and `refusal_reason`.
- Do not invent confidence. Use a conservative score.
- Keep the output as JSON only.
"""

    def _schema_block(self) -> str:
        return """
{
  "title": "Problem Title",
  "domain_tags": ["tag1", "tag2"],
  "objective": "Precise mathematical objective",
  "variables": [
    {"symbol": "x", "description": "variable description", "domain": "ℝ", "type_hint": "float"}
  ],
  "constraints": [
    {"kind": "equation", "expression_latex": "f(x) = 0", "description": "constraint description"}
  ],
  "theoretical_framework": "Relevant theorem, method, or background",
  "expected_output": {
    "kind": "symbolic_expression",
    "description": "What the final answer should look like"
  },
  "confidence": 0.0,
  "assumptions": ["assumption"],
  "ambiguity_notes": ["ambiguity"],
  "dropped_fields": ["field_name"],
  "refusal_reason": "reason or null"
}
""".strip()

    def _validate_formalized_payload(self, data: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        objective = str(data.get("objective") or "").strip()
        if not objective:
            errors.append("Formalized output is missing an objective")

        domain_tags = data.get("domain_tags")
        if not isinstance(domain_tags, list) or not domain_tags:
            errors.append("Formalized output must include at least one domain tag")

        expected_output_data = data.get("expected_output")
        if not isinstance(expected_output_data, dict) or not expected_output_data.get("kind"):
            errors.append("Formalized output has invalid expected_output")

        variables = data.get("variables") or []
        if not isinstance(variables, list):
            errors.append("Formalized output has invalid variables")

        constraints = data.get("constraints") or []
        if not isinstance(constraints, list):
            errors.append("Formalized output has invalid constraints")

        confidence = self._coerce_confidence(data.get("confidence"), 0.0)
        if confidence < MIN_FORMALIZATION_CONFIDENCE:
            errors.append(
                f"Formalization confidence {confidence:.2f} is below the required threshold of {MIN_FORMALIZATION_CONFIDENCE:.2f}"
            )

        ambiguity_notes = self._normalize_string_list(data.get("ambiguity_notes"))
        if ambiguity_notes:
            errors.append("Formalization remains ambiguous and was refused")

        refusal_reason = self._normalize_optional_string(data.get("refusal_reason"))
        if refusal_reason:
            errors.append(refusal_reason)

        return errors

    def _normalize_string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for entry in value:
            text = self._normalize_optional_string(entry)
            if text:
                normalized.append(text)
        return normalized

    def _normalize_optional_string(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _coerce_confidence(self, value: Any, default: float) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, confidence))

    def _preview(self, response_text: str) -> str:
        cleaned = " ".join(response_text.split())
        if len(cleaned) <= MAX_RESPONSE_PREVIEW:
            return cleaned
        return cleaned[: MAX_RESPONSE_PREVIEW - 3] + "..."
