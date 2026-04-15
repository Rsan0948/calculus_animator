from __future__ import annotations

import json

import pytest

from api.bridge import CalculusAPI


@pytest.mark.e2e
def test_backend_smoke_solver_graph_and_learning_slide(monkeypatch):
    # Keep e2e focused on user-facing flows, not startup reporting work.
    monkeypatch.setattr(CalculusAPI, "_auto_generate_capacity_report", lambda self: None)
    api = CalculusAPI()

    solve_payload = json.loads(api.solve(r"\frac{d}{dx}\left(x^3 + \sin(x)\right)"))
    assert solve_payload.get("success") is True
    assert solve_payload.get("steps")
    assert solve_payload.get("animation_steps")

    graph_payload = json.loads(api.get_graph_data(r"x^3 + \sin(x)"))
    assert graph_payload.get("success") is True
    assert graph_payload.get("curves")
    assert isinstance(graph_payload.get("legend"), list)

    curriculum = json.loads(api.get_curriculum())
    pathways = curriculum.get("pathways") or []
    assert pathways, "Curriculum should have at least one pathway for learning flow e2e smoke."
    pathway = pathways[0]
    chapters = pathway.get("chapters") or []
    assert chapters, "First pathway should include chapters for learning flow e2e smoke."
    chapter = chapters[0]

    slide_payload = json.loads(api.render_learning_slide(pathway.get("id"), chapter.get("id"), 0))
    assert slide_payload.get("success") is True
    assert str(slide_payload.get("data_url", "")).startswith("data:image/png;base64,")


@pytest.mark.e2e
def test_backend_smoke_learning_slide_index_clamps(monkeypatch) -> None:
    monkeypatch.setattr(CalculusAPI, "_auto_generate_capacity_report", lambda self: None)
    api = CalculusAPI()
    curriculum = json.loads(api.get_curriculum())

    pathways = curriculum.get("pathways") or []
    assert pathways
    pathway = pathways[0]
    chapters = pathway.get("chapters") or []
    assert chapters
    chapter = chapters[0]
    total = len(chapter.get("slides") or [])
    assert total > 0

    # Very large index should clamp to last slide and still render.
    payload = json.loads(api.render_learning_slide(pathway.get("id"), chapter.get("id"), 99999))
    assert payload.get("success") is True
    # First render returns worker payload; cached render includes explicit slide_index.
    payload_cached = json.loads(api.render_learning_slide(pathway.get("id"), chapter.get("id"), 99999))
    assert int(payload_cached.get("slide_index", -1)) == (total - 1)
