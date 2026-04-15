from __future__ import annotations

import sympy as sp

from math_engine.plugins.calculus.animation_engine import AnimationEngine


def test_safe_sample_broadcasts_scalar_expression() -> None:
    engine = AnimationEngine()
    import numpy as np

    arr = engine._safe_sample(sp.Integer(5), np.array([0.0, 1.0, 2.0]))
    assert arr.shape == (3,)
    assert all(float(v) == 5.0 for v in arr)


def test_generate_graph_data_success_with_asymptote_nulls() -> None:
    engine = AnimationEngine()
    x = sp.Symbol("x")
    out = engine.generate_graph_data(1 / x, x_range=(-1, 1), points=101)
    assert out["success"] is True
    assert len(out["x"]) == len(out["y"]) == 101
    assert any(v is None for v in out["y"])


def test_generate_graph_payload_for_definite_integral_includes_fill_and_guides() -> None:
    engine = AnimationEngine()
    x = sp.Symbol("x")
    out = engine.generate_graph_payload(
        expr=x**2,
        calc_type="INTEGRAL_DEFINITE",
        params={"lower": 0, "upper": 2},
        solved_expr=sp.Rational(8, 3),
    )
    assert out["success"] is True
    assert out["fills"]
    assert len(out["vlines"]) >= 2
    assert "Area [0, 2]" in out["legend"][0] or out["fills"][0]["label"].startswith("Area")


def test_generate_graph_payload_for_limit_includes_limit_guides() -> None:
    engine = AnimationEngine()
    x = sp.Symbol("x")
    out = engine.generate_graph_payload(
        expr=(sp.sin(x) / x),
        calc_type="LIMIT",
        params={"point": 0},
        solved_expr=1,
    )
    assert out["success"] is True
    assert out["vlines"]
    assert out["hlines"]
    assert any("limit" in (h.get("label") or "").lower() for h in out["hlines"])


def test_generate_graph_payload_includes_secondary_curve_when_meaningful() -> None:
    engine = AnimationEngine()
    x = sp.Symbol("x")
    out = engine.generate_graph_payload(
        expr=x**3,
        calc_type="DERIVATIVE",
        solved_expr=3 * x**2,
    )
    assert out["success"] is True
    assert len(out["curves"]) >= 2
    labels = [c["label"] for c in out["curves"]]
    assert "Input function" in labels
    assert any("Derivative" in label for label in labels)


def test_generate_area_frames_returns_expected_count() -> None:
    engine = AnimationEngine()
    x = sp.Symbol("x")
    frames = engine.generate_area_frames(x, 0, 1, frames=12)
    assert len(frames) == 13
    assert frames[0]["frame"] == 0
    assert frames[-1]["frame"] == 12


def test_generate_limit_frames_returns_expected_count() -> None:
    engine = AnimationEngine()
    x = sp.Symbol("x")
    frames = engine.generate_limit_frames((x**2 + 1), point=0, frames=8)
    assert len(frames) == 9
    assert all("approaching" in frame for frame in frames)


def test_generate_tangent_success_payload() -> None:
    engine = AnimationEngine()
    x = sp.Symbol("x")
    out = engine.generate_tangent(x**2, 2 * x, 3)
    assert out["success"] is True
    assert out["point"]["x"] == 3.0
    assert out["slope"] == 6.0
    assert len(out["tangent_x"]) == len(out["tangent_y"]) == 60
