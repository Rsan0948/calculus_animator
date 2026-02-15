from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Tuple
from enum import Enum


class AnimationType(Enum):
    TRANSFORM = "transform"
    HIGHLIGHT = "highlight"
    DRAW = "draw"
    FADE = "fade"
    GRAPH = "graph"
    AREA = "area"
    APPROACH = "approach"
    EXPAND = "expand"


_RULE_CONFIG: Dict[str, Tuple[AnimationType, Mapping[str, object]]] = {
    "power_rule":           (AnimationType.TRANSFORM, {"formula": "nx^{n-1}"}),
    "chain_rule":           (AnimationType.EXPAND,    {"formula": "f'(g(x)) \\cdot g'(x)"}),
    "chain_rule_detail":    (AnimationType.EXPAND,    {"formula": "f'(g(x)) \\cdot g'(x)"}),
    "product_rule":         (AnimationType.EXPAND,    {"formula": "f'g + fg'"}),
    "product_rule_detail":  (AnimationType.EXPAND,    {"formula": "f'g + fg'"}),
    "quotient_rule":        (AnimationType.EXPAND,    {"formula": "\\frac{f'g - fg'}{g^2}"}),
    "quotient_rule_detail": (AnimationType.EXPAND,    {"formula": "\\frac{f'g - fg'}{g^2}"}),
    "sum_rule":             (AnimationType.TRANSFORM, {"formula": "(f+g)' = f'+g'"}),
    "constant_multiple":    (AnimationType.HIGHLIGHT, {"formula": "c \\cdot f'"}),
    "constant":             (AnimationType.FADE,      {}),
    "trig_rule":            (AnimationType.TRANSFORM, {}),
    "exponential_rule":     (AnimationType.TRANSFORM, {}),
    "logarithm_rule":       (AnimationType.TRANSFORM, {}),
    "logarithmic_diff":     (AnimationType.EXPAND,    {}),
    "fundamental_theorem":  (AnimationType.AREA,      {"shade": True}),
    "antiderivative":       (AnimationType.TRANSFORM, {}),
    "integration_result":   (AnimationType.DRAW,      {}),
    "direct_substitution":  (AnimationType.APPROACH,  {}),
    "indeterminate":        (AnimationType.HIGHLIGHT, {"color": "#fbbf24"}),
    "lhopital_or_algebraic":(AnimationType.TRANSFORM, {}),
    "series_expansion":     (AnimationType.EXPAND,    {"sequential": True}),
    "ode_solution":         (AnimationType.DRAW,      {}),
    "simplification":       (AnimationType.FADE,      {}),
    "context_extraction":   (AnimationType.HIGHLIGHT, {"formula": "extract core expression"}),
    "final_result":         (AnimationType.DRAW,      {"final": True}),
}

_DURATIONS = {
    AnimationType.TRANSFORM: 1.0,
    AnimationType.HIGHLIGHT: 0.6,
    AnimationType.DRAW: 1.4,
    AnimationType.FADE: 0.5,
    AnimationType.GRAPH: 2.0,
    AnimationType.AREA: 2.0,
    AnimationType.APPROACH: 1.5,
    AnimationType.EXPAND: 1.2,
}


@dataclass
class AnimationStep:
    step_number: int
    animation_type: AnimationType
    description: str
    latex_before: str
    latex_after: str
    rule_name: str
    duration: float
    visual_hints: Dict[str, object] = field(default_factory=dict)

    def to_dict(self):
        return {
            "step": self.step_number,
            "type": self.animation_type.value,
            "description": self.description,
            "before": self.latex_before,
            "after": self.latex_after,
            "rule": self.rule_name,
            "duration": self.duration,
            "hints": self.visual_hints,
        }


class StepGenerator:
    def generate(self, solver_result: dict, calc_type=None) -> List[AnimationStep]:
        if not solver_result.get("success"):
            return []
        out: List[AnimationStep] = []
        for i, step in enumerate(solver_result.get("steps", [])):
            rule = step.get("rule", "basic")
            atype, hints = _RULE_CONFIG.get(rule, (AnimationType.TRANSFORM, {}))
            out.append(AnimationStep(
                step_number=i + 1,
                animation_type=atype,
                description=step.get("description", ""),
                latex_before=step.get("before", ""),
                latex_after=step.get("after", ""),
                rule_name=rule,
                duration=_DURATIONS.get(atype, 1.0),
                visual_hints=dict(hints.items()),
            ))
        final_latex = str(solver_result.get("result_latex", "") or "")
        if final_latex:
            final_before = out[-1].latex_after if out else ""
            if out and final_before == final_latex:
                final_before = out[-1].latex_before or final_before
            out.append(AnimationStep(
                step_number=len(out) + 1,
                animation_type=AnimationType.DRAW,
                description="Final resolved solution",
                latex_before=final_before,
                latex_after=final_latex,
                rule_name="final_result",
                duration=_DURATIONS.get(AnimationType.DRAW, 1.0),
                visual_hints={"final": True},
            ))
        return out
