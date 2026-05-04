from __future__ import annotations

import base64
import json
from pathlib import Path
from types import SimpleNamespace

import sympy as sp

from api.bridge import CalculusAPI
from core.detector import CalculusType


class _StubStep:
    def __init__(self, payload):
        self._payload = payload

    def to_dict(self):
        return dict(self._payload)


def test_getters_return_json_strings():
    api = CalculusAPI.__new__(CalculusAPI)
    api._learning = {"topics": [{"id": "t1"}]}
    api._curriculum = {"pathways": [{"id": "p1"}]}
    assert json.loads(api.get_learning_library())["topics"][0]["id"] == "t1"
    assert json.loads(api.get_curriculum())["pathways"][0]["id"] == "p1"


def test_solve_contract_success_with_context_extraction_and_animation_steps():
    api = CalculusAPI.__new__(CalculusAPI)
    x = sp.Symbol("x")

    api._detector = SimpleNamespace(detect=lambda latex, explicit=None: CalculusType.DERIVATIVE)
    api._extractor = SimpleNamespace(extract=lambda latex, calc_type, params: ("x^2", {"variable": "x"}))
    api._parser = SimpleNamespace(parse=lambda latex: {"success": True, "sympy_expr": x**2})
    api._solver = SimpleNamespace(
        solve=lambda expr, detected, merged: {
            "success": True,
            "result": 2 * x,
            "result_latex": "2 x",
            "steps": [{"description": "Differentiate", "before": "x^2", "after": "2x", "rule": "power_rule"}],
        }
    )
    api._step_gen = SimpleNamespace(
        generate=lambda result, detected: [
            _StubStep({"step": 1, "type": "transform", "rule": "power_rule"}),
            _StubStep({"step": 2, "type": "draw", "rule": "final_result"}),
        ]
    )
    api._animator = SimpleNamespace(generate_graph_data=lambda expr: {"success": True, "x": [0, 1], "y": [0, 1]})

    raw = api.solve(r"\frac{d}{dx} x^2")
    out = json.loads(raw)
    assert out["success"] is True
    assert out["detected_type"] == "DERIVATIVE"
    assert out["steps"][0]["rule"] == "context_extraction"
    assert len(out["animation_steps"]) == 2
    assert out["result"] == "2*x"
    assert out["graph_original"]["success"] is True


def test_solve_contract_returns_parse_error_when_all_parses_fail():
    api = CalculusAPI.__new__(CalculusAPI)
    api._detector = SimpleNamespace(detect=lambda latex, explicit=None: CalculusType.SIMPLIFY)
    api._extractor = SimpleNamespace(extract=lambda latex, calc_type, params: ("bad", {}))
    api._parser = SimpleNamespace(parse=lambda latex: {"success": False, "error": "Parse failed"})
    api._solver = SimpleNamespace(solve=lambda expr, detected, merged: {"success": False, "error": "n/a"})
    api._step_gen = SimpleNamespace(generate=lambda result, detected: [])
    api._animator = SimpleNamespace(generate_graph_data=lambda expr: {"success": False})
    out = json.loads(api.solve("not math"))
    assert out["success"] is False
    assert "Parse failed" in out["error"]


def test_get_graph_data_contract_success():
    api = CalculusAPI.__new__(CalculusAPI)
    x = sp.Symbol("x")
    api._detector = SimpleNamespace(detect=lambda latex, explicit=None: CalculusType.DERIVATIVE)
    api._extractor = SimpleNamespace(extract=lambda latex, calc_type, params: ("x^3", {"variable": "x"}))
    api._parser = SimpleNamespace(parse=lambda latex: {"success": True, "sympy_expr": x**3})
    api._solver = SimpleNamespace(solve=lambda expr, detected, merged: {"success": True, "result": 3 * x**2})
    api._animator = SimpleNamespace(
        generate_graph_payload=lambda expr, **kwargs: {
            "success": True,
            "curves": [{"label": "Input function", "x": [0, 1], "y": [0, 1]}],
            "legend": ["Input function"],
        }
    )

    out = json.loads(api.get_graph_data("x^3"))
    assert out["success"] is True
    assert out["curves"][0]["label"] == "Input function"


def test_render_learning_slide_uses_cache(monkeypatch):
    api = CalculusAPI.__new__(CalculusAPI)
    api._slide_render_cache = {}
    api._render_worker = None
    api._curriculum = {
        "pathways": [
            {
                "id": "precalculus",
                "chapters": [
                    {
                        "id": "c1",
                        "title": "Functions and Graphs",
                        "slides": [
                            {
                                "id": "s1",
                                "title": "What Is a Function?",
                                "content_blocks": [{"kind": "text", "text": "A function maps each input to one output."}],
                                "graphics": [],
                            }
                        ],
                    }
                ],
            }
        ]
    }

    call_count = {"n": 0}

    def _fake_run_task(payload):
        call_count["n"] += 1
        return {"success": True, "data_url": "data:image/png;base64,AAA"}

    monkeypatch.setattr(api, "_run_render_task", _fake_run_task)

    out1 = json.loads(api.render_learning_slide("precalculus", "c1", 0))
    out2 = json.loads(api.render_learning_slide("precalculus", "c1", 0))
    assert out1["success"] is True
    assert out2["success"] is True
    assert out1["data_url"].startswith("data:image/png;base64,")
    assert call_count["n"] == 1


def test_copy_image_to_clipboard_rejects_invalid_payload():
    api = CalculusAPI.__new__(CalculusAPI)
    out = json.loads(api.copy_image_to_clipboard("not-a-data-url"))
    assert out["success"] is False


def test_copy_image_to_clipboard_success(monkeypatch):
    api = CalculusAPI.__new__(CalculusAPI)
    monkeypatch.setattr("api.bridge.subprocess.check_call", lambda *args, **kwargs: 0)
    payload = "data:image/png;base64," + base64.b64encode(b"fakepng").decode("ascii")
    out = json.loads(api.copy_image_to_clipboard(payload))
    assert out["success"] is True


def test_get_graph_data_returns_parse_error_payload():
    api = CalculusAPI.__new__(CalculusAPI)
    api._detector = SimpleNamespace(detect=lambda latex, explicit=None: CalculusType.SIMPLIFY)
    api._extractor = SimpleNamespace(extract=lambda latex, calc_type, params: ("bad", {}))
    api._parser = SimpleNamespace(parse=lambda latex: {"success": False, "error": "bad parse"})
    api._solver = SimpleNamespace(solve=lambda expr, detected, merged: {"success": False})
    api._animator = SimpleNamespace(generate_graph_payload=lambda *a, **k: {"success": True})
    out = json.loads(api.get_graph_data("bad latex"))
    assert out["success"] is False
    assert "bad parse" in out["error"]


def test_render_learning_slide_error_paths():
    api = CalculusAPI.__new__(CalculusAPI)
    api._slide_render_cache = {}
    api._curriculum = {"pathways": []}
    out = json.loads(api.render_learning_slide("missing", "c", 0))
    assert out["success"] is False
    assert "Pathway not found" in out["error"]

    api._curriculum = {"pathways": [{"id": "p1", "chapters": []}]}
    out = json.loads(api.render_learning_slide("p1", "missing", 0))
    assert out["success"] is False
    assert "Chapter not found" in out["error"]

    api._curriculum = {"pathways": [{"id": "p1", "chapters": [{"id": "c1", "slides": []}]}]}
    out = json.loads(api.render_learning_slide("p1", "c1", 0))
    assert out["success"] is False
    assert "No slides" in out["error"]


def test_extract_pathway_from_content_file_complete_json():
    api = CalculusAPI.__new__(CalculusAPI)
    text = json.dumps({"pathway": {"id": "precalculus", "chapters": [{"id": "c1"}]}})
    pathway = api._extract_pathway_from_content_file(text)
    assert pathway["id"] == "precalculus"
    assert pathway["chapters"][0]["id"] == "c1"


def test_extract_pathway_from_content_file_with_minor_repair():
    api = CalculusAPI.__new__(CalculusAPI)
    # malformed duplicate opener before chapter item should be repaired
    broken = (
        '{\n  "pathway": {\n    "id": "precalculus",\n    "chapters": [\n'
        '    {\n      {\n        "id": "c1"\n      }\n    ]\n  }\n}'
    )
    pathway = api._extract_pathway_from_content_file(broken)
    assert pathway is not None
    assert pathway["id"] == "precalculus"


def test_extract_pathway_from_content_file_truncation_fallback():
    api = CalculusAPI.__new__(CalculusAPI)
    marker = ',\n          {\n            "id": "precalc_ch5_s12"'
    fixture = Path(__file__).parent / "fixtures" / "content_jsons_sample.txt"
    text = fixture.read_text(encoding="utf-8")
    pos = text.find(marker)
    assert pos != -1
    truncated = text[: pos + len(marker) + 4]
    pathway = api._extract_pathway_from_content_file(truncated)
    assert pathway is not None
    assert pathway["id"] == "precalculus"


def test_normalize_learning_library_legacy_conversion():
    api = CalculusAPI.__new__(CalculusAPI)
    legacy = {
        "symbols": [{"id": "sym_limit", "label": "lim", "plain_explanation": "limit"}],
        "formulas": [{"id": "f_power", "name": "Power Rule", "plain_math": "d/dx x^n = nx^(n-1)", "latex": r"\frac{d}{dx}x^n"}],
        "examples": [{"id": "ex1", "title": "Example 1", "problem_plain_math": "d/dx x^2", "steps": [{"after_plain_math": "2x", "explanation": "differentiate"}]}],
        "concepts": [{
            "id": "topic_derivatives",
            "category": "Derivatives",
            "title": "Derivatives Intro",
            "summary": "rate of change",
            "plain_explanation": "A derivative measures change.",
            "symbol_ids": ["sym_limit"],
            "formula_ids": ["f_power"],
            "example_ids": ["ex1"],
            "related_concept_ids": [],
        }],
    }
    out = api._normalize_learning_library(legacy)
    assert "categories" in out and out["categories"]
    assert "topics" in out and out["topics"]
    assert out["topics"][0]["examples"][0]["steps"][0]["math"] == "2x"


def test_normalize_learning_library_passthrough_shape():
    api = CalculusAPI.__new__(CalculusAPI)
    raw = {"categories": [], "symbols": [], "formulas": [], "topics": []}
    out = api._normalize_learning_library(raw)
    assert out is raw


def test_slug_helper():
    api = CalculusAPI.__new__(CalculusAPI)
    assert api._slug("Functions & Graphs") == "functions__graphs"
    assert api._slug("") == "general"


def test_load_curriculum_data_fallback_when_extract_raises(monkeypatch):
    api = CalculusAPI.__new__(CalculusAPI)
    monkeypatch.setattr(api, "_load_json", lambda name, default: {"pathways": [{"id": "fallback"}]})
    monkeypatch.setattr(api, "_extract_pathway_from_content_file", lambda _text: (_ for _ in ()).throw(RuntimeError("boom")))
    out = api._load_curriculum_data()
    assert out["pathways"][0]["id"] == "fallback"


def test_load_learning_library_uses_normalizer(monkeypatch):
    api = CalculusAPI.__new__(CalculusAPI)
    called = {"n": 0}

    def _norm(raw):
        called["n"] += 1
        return {"categories": [], "symbols": raw.get("symbols", []), "formulas": [], "topics": []}

    monkeypatch.setattr(api, "_normalize_learning_library", _norm)
    out = api._load_learning_library()
    assert "symbols" in out
    assert called["n"] == 1


def test_constructor_initializes_core_fields(monkeypatch):
    monkeypatch.setattr(CalculusAPI, "_auto_generate_capacity_report", lambda self: None)
    monkeypatch.setattr(CalculusAPI, "_load_json", lambda self, name, default: default)
    monkeypatch.setattr(CalculusAPI, "_load_learning_library", lambda self: {"categories": [], "symbols": [], "formulas": [], "topics": []})
    monkeypatch.setattr(CalculusAPI, "_load_curriculum_data", lambda self: {"pathways": []})
    api = CalculusAPI()
    assert hasattr(api, "_parser")
    assert hasattr(api, "_animator")
    assert api._slide_render_cache == {}


def test_get_area_animation_and_tangent_paths():
    api = CalculusAPI.__new__(CalculusAPI)
    x = sp.Symbol("x")
    api._extractor = SimpleNamespace(extract=lambda latex: ("x^2", {}))
    api._parser = SimpleNamespace(parse=lambda latex: {"success": True, "sympy_expr": x**2})
    api._animator = SimpleNamespace(
        generate_area_frames=lambda expr, lo, hi: [{"frame": 0, "x": [0], "y": [0]}],
        generate_tangent=lambda expr, deriv, x_pt: {"success": True, "point": {"x": x_pt, "y": 1}, "slope": 2},
    )
    area = json.loads(api.get_area_animation("x^2", 0, 1))
    assert "frames" in area and area["frames"]

    tan = json.loads(api.get_tangent_data("x^2", "2x", 1.0))
    assert tan["success"] is True
    assert tan["slope"] == 2
