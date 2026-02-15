from __future__ import annotations

import io
import json
import sys
import types

from api import slide_render_worker as worker


def test_pretty_math_text_formats_exponents_and_fractions():
    text = r"\frac{d^5}{dx^5} \left(x^3 \sin(x^2)\right)"
    out = worker._pretty_math_text(text)
    assert "d" in out
    assert "sin" in out
    assert "⁵" in out


def test_sup_and_sub_maps_produce_unicode():
    assert worker._to_sup("12x") == "¹²ˣ"
    assert worker._to_sub("12x") == "₁₂ₓ"


def test_build_data_url_with_stubbed_modules(monkeypatch):
    fake_pygame = types.ModuleType("pygame")
    fake_pygame.init = lambda: None
    fake_pygame.font = types.SimpleNamespace(init=lambda: None)

    def _save(_surface, path):
        with open(path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\nstub")

    fake_pygame.image = types.SimpleNamespace(save=_save)

    fake_slide_renderer = types.ModuleType("slide_renderer")

    class FakeSlideEngine:
        def __init__(self, *args, **kwargs):
            self._slides = []

        def add_slide(self, slide):
            self._slides.append(slide)

        def render_slide_to_surface(self, index=0, width=1200, height=675):
            return object()

    class FakeSlide:
        def __init__(self, *args, **kwargs):
            self.items = []

        def add(self, item):
            self.items.append(item)

    class _Dummy:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    fake_slide_renderer.SlideEngine = FakeSlideEngine
    fake_slide_renderer.Slide = FakeSlide
    fake_slide_renderer.TextBox = _Dummy
    fake_slide_renderer.BulletList = _Dummy
    fake_slide_renderer.Shape = _Dummy

    monkeypatch.setitem(sys.modules, "pygame", fake_pygame)
    monkeypatch.setitem(sys.modules, "slide_renderer", fake_slide_renderer)

    payload = {
        "chapter_title": "Functions",
        "slide_title": "What Is a Function?",
        "slide_index": 0,
        "slide_total": 10,
        "content_blocks": [{"kind": "text", "text": "A function maps input to one output."}],
        "graphics": [],
        "width": 1000,
        "height": 620,
    }
    data_url = worker._build_data_url(payload)
    assert data_url.startswith("data:image/png;base64,")


def test_main_success_and_failure_paths(monkeypatch):
    # success path
    monkeypatch.setattr(worker, "_build_data_url", lambda payload: "data:image/png;base64,AAA")
    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    out_stream = io.StringIO()
    monkeypatch.setattr("sys.stdout", out_stream)
    code = worker.main()
    assert code == 0
    out = json.loads(out_stream.getvalue())
    assert out["success"] is True

    # failure path
    def _boom(_payload):
        raise RuntimeError("render failed")

    monkeypatch.setattr(worker, "_build_data_url", _boom)
    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    out_stream = io.StringIO()
    monkeypatch.setattr("sys.stdout", out_stream)
    code = worker.main()
    assert code == 1
    out = json.loads(out_stream.getvalue())
    assert out["success"] is False
    assert "render failed" in out["error"]
