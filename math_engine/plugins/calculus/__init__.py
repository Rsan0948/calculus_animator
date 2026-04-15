"""Compatibility shim — core has moved to math_engine.plugins.calculus."""

from math_engine.plugins.calculus.animation_engine import AnimationEngine
from math_engine.plugins.calculus.detector import CalculusType, TypeDetector
from math_engine.plugins.calculus.extractor import ExpressionExtractor
from math_engine.plugins.calculus.parser import ExpressionParser
from math_engine.plugins.calculus.slide_highlighting import build_informative_slide_highlights
from math_engine.plugins.calculus.solver import CalculusSolver
from math_engine.plugins.calculus.step_generator import StepGenerator

__all__ = [
    "AnimationEngine",
    "CalculusType",
    "TypeDetector",
    "ExpressionExtractor",
    "ExpressionParser",
    "build_informative_slide_highlights",
    "CalculusSolver",
    "StepGenerator",
]
