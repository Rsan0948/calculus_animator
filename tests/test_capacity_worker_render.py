from __future__ import annotations

import io
import json

from api import capacity_slide_worker as worker


def test_render_metrics_only_true_returns_expected_metrics() -> None:
    payload = {
        "text": "[CHK-001] synthetic calibration sentence.",
        "width": 800,
        "height": 520,
        "with_image": False,
        "page_index": 0,
        "metrics_only": True,
    }
    out = worker._render(payload)
    assert out["success"] is True
    assert out["total_pages"] >= 1
    assert out["chars_on_page"] >= 1
    assert "page_text" in out


def test_render_metrics_only_false_returns_data_url() -> None:
    payload = {
        "text": "[CHK-001] synthetic calibration sentence to render output image.",
        "width": 900,
        "height": 560,
        "with_image": True,
        "page_index": 0,
        "metrics_only": False,
    }
    out = worker._render(payload)
    assert out["success"] is True
    assert out["data_url"].startswith("data:image/png;base64,")


def test_main_emits_error_json_on_invalid_input(monkeypatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("{"))
    out_stream = io.StringIO()
    monkeypatch.setattr("sys.stdout", out_stream)
    code = worker.main()
    assert code == 1
    payload = json.loads(out_stream.getvalue())
    assert payload["success"] is False
    assert "error" in payload
