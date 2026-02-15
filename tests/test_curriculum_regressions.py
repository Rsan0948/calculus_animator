from __future__ import annotations

from pathlib import Path

from api.bridge import CalculusAPI


ROOT = Path(__file__).resolve().parent.parent


def test_content_jsons_parses_into_pathway_with_extended_chapters():
    api = CalculusAPI.__new__(CalculusAPI)
    text = (ROOT / "content_jsons.txt").read_text(encoding="utf-8")
    pathway = api._extract_pathway_from_content_file(text)
    assert pathway is not None
    assert pathway.get("id") == "precalculus"
    chapters = pathway.get("chapters") or []
    assert len(chapters) >= 8
    assert any((c.get("id") or "").startswith("precalc_ch8") for c in chapters)


def test_load_curriculum_data_prefers_content_jsons_pathway_first():
    api = CalculusAPI.__new__(CalculusAPI)
    curriculum = api._load_curriculum_data()
    pathways = curriculum.get("pathways") or []
    assert pathways
    assert pathways[0].get("id") == "precalculus"
    chapters = pathways[0].get("chapters") or []
    assert len(chapters) >= 8


def test_slide_highlight_builder_outputs_concise_nonempty_items():
    blocks = [
        {"kind": "problem", "text": "Find the derivative of x^3 sin(x)."},
        {
            "kind": "text",
            "text": "Use the product rule because this is a product of two functions. Differentiate each factor and combine terms carefully.",
        },
        {"kind": "note", "text": "Note: Keep like terms grouped for readability."},
    ]
    highlights = CalculusAPI._build_slide_highlights(blocks)
    assert 1 <= len(highlights) <= 5
    assert any("Problem:" in item["text"] for item in highlights)
    assert all(item["text"].strip() for item in highlights)

