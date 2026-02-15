from __future__ import annotations

import hashlib
import json
from pathlib import Path

from api.bridge import CalculusAPI
from core.detector import TypeDetector
from core.extractor import ExpressionExtractor
from core.parser import ExpressionParser
from core.solver import CalculusSolver
from core.step_generator import StepGenerator


ROOT = Path(__file__).resolve().parent.parent
SNAP_DIR = ROOT / "tests" / "snapshots"


def _sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_demo_solver_snapshots_match_baseline():
    demo_data = _load_json(ROOT / "data" / "demo_problems.json")
    snap = _load_json(SNAP_DIR / "demo_solver_snapshots.json")
    expected = {d["id"]: d for d in snap["demos"]}

    parser = ExpressionParser()
    extractor = ExpressionExtractor()
    detector = TypeDetector()
    solver = CalculusSolver()
    stepgen = StepGenerator()

    demo_map = {}
    for coll in demo_data.get("collections", []):
        for d in coll.get("demos", []):
            demo_map[d["id"]] = d

    for demo_id, exp in expected.items():
        assert demo_id in demo_map, f"Snapshot demo id not found in demo data: {demo_id}"
        d = demo_map[demo_id]
        detected = detector.detect(d["latex"], d.get("tag"))
        inner, params = extractor.extract(d["latex"], d.get("tag"), d.get("params") or {})
        parsed = parser.parse(inner)
        if not parsed.get("success"):
            parsed = parser.parse(d["latex"])
        assert parsed.get("success"), f"Parsing failed for demo {demo_id}: {parsed}"
        solved = solver.solve(parsed["sympy_expr"], detected, params)
        assert solved.get("success"), f"Solving failed for demo {demo_id}: {solved}"
        anim = stepgen.generate(solved, detected)

        got = {
            "id": demo_id,
            "detected_type": detected.name,
            "inner_latex": inner,
            "step_count": len(solved.get("steps", [])),
            "rules": [s.get("rule") for s in solved.get("steps", [])],
            "animation_step_count": len(anim),
            "animation_rules": [a.rule_name for a in anim],
            "result_latex_hash": _sha(solved.get("result_latex", "")),
        }
        assert got == exp, (
            f"Demo snapshot mismatch for {demo_id}.\n"
            f"Expected: {json.dumps(exp, indent=2)}\n"
            f"Got: {json.dumps(got, indent=2)}"
        )


def test_learning_slide_highlight_snapshots_match_baseline():
    snap = _load_json(SNAP_DIR / "learning_slide_highlight_snapshots.json")
    expected = snap["slides"]

    api = CalculusAPI.__new__(CalculusAPI)
    curriculum = api._load_curriculum_data()
    pathways = curriculum.get("pathways") or []
    precalc = next((p for p in pathways if p.get("id") == "precalculus"), None)
    assert precalc is not None, "precalculus pathway not found"

    chapter_map = {c.get("id"): c for c in (precalc.get("chapters") or [])}
    for exp in expected:
        ch = chapter_map.get(exp["chapter_id"])
        assert ch is not None, f"Chapter missing for snapshot: {exp['chapter_id']}"
        slide = next((s for s in (ch.get("slides") or []) if s.get("id") == exp["slide_id"]), None)
        assert slide is not None, f"Slide missing for snapshot: {exp['slide_id']}"
        highlights = api._build_slide_highlights(slide.get("content_blocks") or [])
        joined = "\n".join(h["text"] for h in highlights)
        got = {
            "chapter_id": exp["chapter_id"],
            "slide_id": exp["slide_id"],
            "title": slide.get("title"),
            "highlight_count": len(highlights),
            "highlight_hash": _sha(joined),
        }
        assert got == exp, (
            f"Learning-slide snapshot mismatch for {exp['slide_id']}.\n"
            f"Expected: {json.dumps(exp, indent=2)}\n"
            f"Got: {json.dumps(got, indent=2)}"
        )

