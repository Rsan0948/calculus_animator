from __future__ import annotations

from math_engine.plugins.calculus.detector import CalculusType, TypeDetector


def test_detect_honors_explicit_tag() -> None:
    detector = TypeDetector()
    assert detector.detect("x^2", explicit_tag="limit") == CalculusType.LIMIT
    assert detector.detect("x^2", explicit_tag="unknown-tag") == CalculusType.UNKNOWN


def test_detect_definite_integral_before_indefinite() -> None:
    detector = TypeDetector()
    detected = detector.detect(r"\int_{0}^{1} x^2 dx")
    assert detected == CalculusType.INTEGRAL_DEFINITE


def test_detect_derivative_pattern() -> None:
    detector = TypeDetector()
    detected = detector.detect(r"\frac{d}{dx} x^3")
    assert detected == CalculusType.DERIVATIVE


def test_detect_limit_pattern() -> None:
    detector = TypeDetector()
    detected = detector.detect(r"\lim_{x \to \infty} \left(1+\frac{1}{x}\right)^x")
    assert detected == CalculusType.LIMIT


def test_default_to_simplify_when_no_pattern_matches() -> None:
    detector = TypeDetector()
    detected = detector.detect("x^2 + 4x + 4")
    assert detected == CalculusType.SIMPLIFY
