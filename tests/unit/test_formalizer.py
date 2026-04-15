"""Tests for strict multi-pass formalization."""

import pytest

from engine.state import SourceDocument
from ingestion.formalization.formalizer import FormalizationError, Formalizer


def test_formalize_with_report_accepts_valid_multi_pass_output(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        '{"title": "Derivative Problem", "objective": "differentiate x^2"}',
        """
        {
          "title": "Derivative Problem",
          "domain_tags": ["calculus"],
          "objective": "differentiate x^2",
          "variables": [{"symbol": "x", "description": "input", "domain": "R", "type_hint": "float"}],
          "constraints": [],
          "theoretical_framework": "basic differentiation",
          "expected_output": {"kind": "symbolic_expression", "description": "derivative"},
          "confidence": 0.91,
          "assumptions": ["The function is differentiable"],
          "ambiguity_notes": [],
          "dropped_fields": [],
          "refusal_reason": null
        }
        """,
    ]

    def fake_call(self: Formalizer, prompt: str, system: str) -> str:
        return responses.pop(0)

    monkeypatch.setattr(Formalizer, "_call_llm_with_retry", fake_call)

    formalizer = Formalizer(model="test-model")
    problem, report = formalizer.formalize_with_report(
        ["# Problem\nDifferentiate x^2", "Provide the symbolic derivative."],
        source_doc=SourceDocument(format="pdf", title="paper"),
    )

    assert problem is not None
    assert problem.objective == "differentiate x^2"
    assert problem.confidence == pytest.approx(0.91)
    assert report.accepted is True
    assert report.confidence == pytest.approx(0.91)
    assert report.assumptions == ["The function is differentiable"]
    assert [attempt.phase for attempt in report.attempts] == ["extract", "repair", "validate"]
    assert all(attempt.success for attempt in report.attempts)


def test_formalize_refuses_ambiguous_low_confidence_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def build_responses() -> list[str]:
        return [
            '{"title": "Unclear Problem", "objective": "maybe optimize something"}',
            """
            {
              "title": "Unclear Problem",
              "domain_tags": ["optimization"],
              "objective": "maybe optimize something",
              "variables": [],
              "constraints": [],
              "theoretical_framework": "",
              "expected_output": {"kind": "algorithm", "description": "candidate method"},
              "confidence": 0.42,
              "assumptions": ["The excerpt omitted key constraints"],
              "ambiguity_notes": ["The objective is underspecified"],
              "dropped_fields": ["constraints"],
              "refusal_reason": "Insufficient detail to build a reliable problem statement"
            }
            """,
        ]

    responses = build_responses()

    def fake_call(self: Formalizer, prompt: str, system: str) -> str:
        return responses.pop(0)

    monkeypatch.setattr(Formalizer, "_call_llm_with_retry", fake_call)

    formalizer = Formalizer(model="test-model")
    problem, report = formalizer.formalize_with_report(
        ["This excerpt gestures at an optimization problem without equations."],
        source_doc=SourceDocument(format="pdf", title="paper"),
    )

    assert problem is None
    assert report.accepted is False
    assert report.confidence == pytest.approx(0.42)
    assert report.refusal_reason == "Insufficient detail to build a reliable problem statement"
    assert any("below the required threshold" in error for error in report.validation_errors)
    assert any("ambiguous" in error.lower() for error in report.validation_errors)

    responses = build_responses()
    with pytest.raises(FormalizationError, match="Insufficient detail"):
        formalizer.formalize(
            ["This excerpt gestures at an optimization problem without equations."],
            source_doc=SourceDocument(format="pdf", title="paper"),
        )
