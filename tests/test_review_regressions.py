"""Regression tests for the deep-review fixes to the core solver pipeline.

Each test pins a previously-broken behavior:

1. Unevaluated integrals (indefinite AND definite) must report failure,
   never a raw ``Integral(...)`` presented as a solved answer.
2. Definite integrals that evaluate without an elementary antiderivative
   (e.g. the Gaussian) still succeed, with honest steps.
3. The type detector must not route ``\\int f'(x) dx`` (prime inside an
   integrand) or ``\\int \\frac{dq}{q}`` to the derivative solver, while a
   leading d/dx operator (FTC expressions) still wins.
4. Composite trig/exp/log derivatives are labelled ``chain_rule``.
5. The step generator's terminal final-result step survives the
   MAX_ANIMATION_STEPS cap.
6. ``generate_area_frames(frames=0)`` clamps instead of silently
   returning an empty animation from a swallowed ZeroDivisionError.
7. The bridge slide-render cache evicts LRU (a cache hit refreshes
   recency), not FIFO.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import sympy as sp

from api.bridge import CalculusAPI
from config import MAX_ANIMATION_STEPS
from core.animation_engine import AnimationEngine
from core.detector import CalculusType, TypeDetector
from core.solver import CalculusSolver
from core.step_generator import StepGenerator

X = sp.Symbol("x")


# ─────────────────────────────────────────────────────────────────────────────
# 1-2. Unevaluated integrals
# ─────────────────────────────────────────────────────────────────────────────


def test_indefinite_integral_without_closed_form_fails_honestly():
    solver = CalculusSolver()
    # sin(x)/x * exp(x^2) has no elementary antiderivative; SymPy returns an
    # unevaluated Integral node.
    out = solver.solve(sp.sin(X) / X * sp.exp(X**2), CalculusType.INTEGRAL_INDEFINITE)
    assert out["success"] is False
    assert "antiderivative" in out["error"].lower()
    # The failure shape must not leak a raw Integral(...) as the result.
    assert "Integral(" not in str(out.get("result", ""))


def test_definite_integral_without_closed_form_fails_honestly():
    solver = CalculusSolver()
    out = solver.solve(
        sp.sin(X) / X * sp.exp(X**2),
        CalculusType.INTEGRAL_DEFINITE,
        {"lower": 0, "upper": 1},
    )
    assert out["success"] is False
    assert "definite integral" in out["error"].lower()


def test_definite_integral_gaussian_evaluates_without_elementary_antiderivative():
    solver = CalculusSolver()
    out = solver.solve(
        sp.exp(-(X**2)),
        CalculusType.INTEGRAL_DEFINITE,
        {"lower": "-oo", "upper": "oo"},
    )
    assert out["success"] is True
    assert sp.sympify(out["result"]) == sp.sqrt(sp.pi)
    # The F(b)-F(a) steps would render an unevaluated Integral (erf-free
    # build path); the single honest evaluation step is used instead, and
    # no step may contain a raw unevaluated Integral repr.
    assert out["steps"], "expected at least one step"
    for step in out["steps"]:
        assert "Integral(" not in step["after"]


def test_definite_integral_normal_keeps_full_ftc_steps():
    solver = CalculusSolver()
    out = solver.solve(X**2, CalculusType.INTEGRAL_DEFINITE, {"lower": 0, "upper": 1})
    assert out["success"] is True
    assert sp.sympify(out["result"]) == sp.Rational(1, 3)
    assert [s["rule"] for s in out["steps"]] == ["antiderivative", "fundamental_theorem"]


# ─────────────────────────────────────────────────────────────────────────────
# 3. Detector routing
# ─────────────────────────────────────────────────────────────────────────────


def test_detector_prime_inside_integrand_routes_to_integral():
    detector = TypeDetector()
    assert detector.detect(r"\int f'(x)\,dx") == CalculusType.INTEGRAL_INDEFINITE
    assert detector.detect(r"\int_0^1 f'(x)\,dx") == CalculusType.INTEGRAL_DEFINITE


def test_detector_d_fraction_inside_integrand_routes_to_integral():
    detector = TypeDetector()
    assert detector.detect(r"\int \frac{dq}{q}") == CalculusType.INTEGRAL_INDEFINITE


def test_detector_leading_derivative_operator_wins_over_inner_integral():
    # FTC expressions are derivatives even though the body has \int_.
    detector = TypeDetector()
    assert detector.detect(r"\frac{d}{dx} \int_0^x f(t)\,dt") == CalculusType.DERIVATIVE


def test_detector_prime_in_limit_body_routes_to_limit():
    detector = TypeDetector()
    assert detector.detect(r"\lim_{h \to 0} f'(x+h)") == CalculusType.LIMIT


def test_detector_plain_prime_still_derivative():
    detector = TypeDetector()
    assert detector.detect(r"f'(x)") == CalculusType.DERIVATIVE
    assert detector.detect(r"(x^2)'") == CalculusType.DERIVATIVE


def test_detector_ode_still_wins_over_everything():
    detector = TypeDetector()
    assert detector.detect(r"y' + y = 0") == CalculusType.DIFFERENTIAL_EQ


# ─────────────────────────────────────────────────────────────────────────────
# 4. Chain-rule labelling for composite elementary functions
# ─────────────────────────────────────────────────────────────────────────────


def test_composite_trig_exp_log_labelled_chain_rule():
    solver = CalculusSolver()
    assert solver._identify_diff_rule(sp.sin(X**2), X) == "chain_rule"
    assert solver._identify_diff_rule(sp.cos(3 * X), X) == "chain_rule"
    assert solver._identify_diff_rule(sp.exp(X**2), X) == "chain_rule"
    assert solver._identify_diff_rule(sp.log(X**2 + 1), X) == "chain_rule"


def test_bare_trig_exp_log_keep_elementary_rule_labels():
    solver = CalculusSolver()
    assert solver._identify_diff_rule(sp.sin(X), X) == "trig_rule"
    assert solver._identify_diff_rule(sp.exp(X), X) == "exponential_rule"
    assert solver._identify_diff_rule(sp.log(X), X) == "logarithm_rule"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Step-cap truncation keeps the final-result step
# ─────────────────────────────────────────────────────────────────────────────


def _fake_solver_result(n_steps: int) -> dict:
    return {
        "success": True,
        "result_latex": "FINAL",
        "steps": [
            {"description": f"s{i}", "before": "a", "after": "b", "rule": "basic"}
            for i in range(n_steps)
        ],
    }


def test_final_step_survives_exact_cap_boundary():
    out = StepGenerator().generate(_fake_solver_result(MAX_ANIMATION_STEPS))
    assert len(out) == MAX_ANIMATION_STEPS
    assert out[-1].rule_name == "final_result"
    assert out[-1].latex_after == "FINAL"
    assert out[-1].step_number == MAX_ANIMATION_STEPS


def test_final_step_survives_far_over_cap():
    out = StepGenerator().generate(_fake_solver_result(MAX_ANIMATION_STEPS * 3))
    assert len(out) == MAX_ANIMATION_STEPS
    assert out[-1].rule_name == "final_result"


def test_under_cap_output_is_untouched():
    out = StepGenerator().generate(_fake_solver_result(3))
    assert len(out) == 4  # 3 solver steps + final
    assert [s.step_number for s in out] == [1, 2, 3, 4]
    assert out[-1].rule_name == "final_result"


# ─────────────────────────────────────────────────────────────────────────────
# 6. Area frames clamp
# ─────────────────────────────────────────────────────────────────────────────


def test_area_frames_zero_and_negative_clamp_to_one():
    engine = AnimationEngine()
    for frames in (0, -5):
        out = engine.generate_area_frames(X**2, 0, 1, frames=frames)
        assert len(out) == 2  # frames=1 → i in {0, 1}
        assert out[-1]["fill_to"] == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# 7. Bridge slide-render cache is LRU, not FIFO
# ─────────────────────────────────────────────────────────────────────────────


def _api_with_chapter(n_slides: int) -> CalculusAPI:
    api = CalculusAPI.__new__(CalculusAPI)
    api._slide_render_cache = {}
    api._curriculum = {
        "pathways": [
            {
                "id": "p1",
                "chapters": [
                    {
                        "id": "c1",
                        "title": "Chapter",
                        "slides": [
                            {
                                "id": f"s{i}",
                                "title": f"Slide {i}",
                                "content_blocks": [{"kind": "text", "text": f"body {i}"}],
                                "graphics": [],
                            }
                            for i in range(n_slides)
                        ],
                    }
                ],
            }
        ]
    }
    return api


def test_slide_render_cache_evicts_lru_not_fifo(monkeypatch):
    cap = 120
    api = _api_with_chapter(cap + 2)
    rendered = []

    def _fake_run_task(payload):
        rendered.append(payload["slide_index"])
        return {"success": True, "data_url": f"data:image/png;base64,{payload['slide_index']}"}

    monkeypatch.setattr(api, "_run_render_task", _fake_run_task)

    # Fill the cache exactly to capacity with slides 0..cap-1.
    for i in range(cap):
        json.loads(api.render_learning_slide("p1", "c1", i))
    assert len(api._slide_render_cache) == cap

    # Touch slide 0 (cache hit) to refresh its recency.
    before = len(rendered)
    out = json.loads(api.render_learning_slide("p1", "c1", 0))
    assert out["success"] is True
    assert len(rendered) == before, "cache hit must not re-render"

    # Insert one more slide: with LRU the evictee is slide 1 (oldest
    # untouched), NOT slide 0. Under the old FIFO behavior slide 0 —
    # the most recently viewed slide — would have been evicted.
    json.loads(api.render_learning_slide("p1", "c1", cap))
    before = len(rendered)
    json.loads(api.render_learning_slide("p1", "c1", 0))
    assert len(rendered) == before, "slide 0 should still be cached after LRU eviction"
    json.loads(api.render_learning_slide("p1", "c1", 1))
    assert rendered[-1] == 1, "slide 1 (LRU) should have been evicted and re-rendered"


def test_capacity_report_generation_is_a_noop():
    # The capacity metrics are stubbed out; startup must not walk the
    # curriculum computing discarded placeholder rows.
    api = CalculusAPI.__new__(CalculusAPI)
    api._curriculum = SimpleNamespace()  # would raise if the old walk ran
    api._auto_generate_capacity_report()  # must not touch _curriculum
