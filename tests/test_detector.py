from __future__ import annotations

from core.detector import CalculusType, TypeDetector


def test_detect_honors_explicit_tag():
    detector = TypeDetector()
    assert detector.detect("x^2", explicit_tag="limit") == CalculusType.LIMIT
    assert detector.detect("x^2", explicit_tag="unknown-tag") == CalculusType.UNKNOWN


def test_detect_definite_integral_before_indefinite():
    detector = TypeDetector()
    detected = detector.detect(r"\int_{0}^{1} x^2 dx")
    assert detected == CalculusType.INTEGRAL_DEFINITE


def test_detect_derivative_pattern():
    detector = TypeDetector()
    detected = detector.detect(r"\frac{d}{dx} x^3")
    assert detected == CalculusType.DERIVATIVE


def test_detect_limit_pattern():
    detector = TypeDetector()
    detected = detector.detect(r"\lim_{x \to \infty} \left(1+\frac{1}{x}\right)^x")
    assert detected == CalculusType.LIMIT


def test_default_to_simplify_when_no_pattern_matches():
    detector = TypeDetector()
    detected = detector.detect("x^2 + 4x + 4")
    assert detected == CalculusType.SIMPLIFY

