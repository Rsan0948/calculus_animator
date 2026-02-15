from __future__ import annotations

from core.step_generator import AnimationType, StepGenerator


def test_generate_returns_empty_for_unsuccessful_solver_result():
    generator = StepGenerator()
    steps = generator.generate({"success": False})
    assert steps == []


def test_generate_maps_rule_to_animation_type_and_appends_final():
    generator = StepGenerator()
    solver_result = {
        "success": True,
        "steps": [
            {
                "description": "Use product rule",
                "before": r"x^2 \sin(x)",
                "after": r"2x\sin(x)+x^2\cos(x)",
                "rule": "product_rule",
            }
        ],
        "result_latex": r"2x\sin(x)+x^2\cos(x)",
    }
    steps = generator.generate(solver_result)
    assert len(steps) == 2
    assert steps[0].animation_type == AnimationType.EXPAND
    assert steps[0].visual_hints["formula"] == "f'g + fg'"
    assert steps[1].rule_name == "final_result"
    assert steps[1].visual_hints["final"] is True


def test_final_step_uses_previous_before_when_after_equals_final_latex():
    generator = StepGenerator()
    solver_result = {
        "success": True,
        "steps": [
            {
                "description": "Simplify",
                "before": r"x^2\cos(x)+2x\sin(x)",
                "after": r"2x\sin(x)+x^2\cos(x)",
                "rule": "simplification",
            }
        ],
        "result_latex": r"2x\sin(x)+x^2\cos(x)",
    }
    steps = generator.generate(solver_result)
    assert len(steps) == 2
    assert steps[1].latex_before == r"x^2\cos(x)+2x\sin(x)"
    assert steps[1].description == "Final resolved solution"


def test_no_final_step_when_result_latex_missing():
    generator = StepGenerator()
    solver_result = {
        "success": True,
        "steps": [
            {"description": "A", "before": "x", "after": "1", "rule": "basic"},
        ],
        "result_latex": "",
    }
    steps = generator.generate(solver_result)
    assert len(steps) == 1
    assert steps[0].rule_name == "basic"
