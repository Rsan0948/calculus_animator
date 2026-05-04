from __future__ import annotations

import io
import json
import queue
import threading
from types import SimpleNamespace

from api import bridge
from api import capacity_slide_worker as worker


def test_render_metrics_only_true_returns_expected_metrics():
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


def test_render_metrics_only_false_returns_data_url():
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


def test_main_emits_error_json_on_invalid_input(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("{"))
    out_stream = io.StringIO()
    monkeypatch.setattr("sys.stdout", out_stream)
    code = worker.main()
    assert code == 1
    payload = json.loads(out_stream.getvalue())
    assert payload["success"] is False
    assert "error" in payload


# ── Bridge worker reliability tests ──────────────────────────────


def _capture_logger(monkeypatch):
    """Replace bridge.logger with a recording stub and return the captured list."""
    captured = []

    def _record(level: str):
        def _log(fmt, *args):
            try:
                captured.append((level, fmt % args if args else fmt))
            except (TypeError, ValueError):
                captured.append((level, fmt))
        return _log

    fake_logger = SimpleNamespace(
        warning=_record("warning"),
        error=_record("error"),
        info=_record("info"),
        debug=_record("debug"),
    )
    monkeypatch.setattr(bridge, "logger", fake_logger)
    return captured


def test_drain_stream_to_logger_forwards_lines_and_handles_close(monkeypatch):
    captured = _capture_logger(monkeypatch)
    stream = io.StringIO("first warning\nsecond warning\n\n")
    bridge._drain_stream_to_logger(stream, "render-worker-test")
    warnings = [msg for level, msg in captured if level == "warning"]
    assert any("first warning" in m for m in warnings)
    assert any("second warning" in m for m in warnings)
    assert stream.closed


def test_drain_stream_to_logger_tolerates_none_stream(monkeypatch):
    _capture_logger(monkeypatch)
    bridge._drain_stream_to_logger(None, "render-worker-test")


def test_read_stdout_to_queue_forwards_then_signals_eof():
    q: "queue.Queue" = queue.Queue()
    stream = io.StringIO('{"success": true}\n')
    bridge._read_stdout_to_queue(stream, q)
    first = q.get_nowait()
    sentinel = q.get_nowait()
    assert first == '{"success": true}\n'
    assert sentinel is None
    assert stream.closed


def test_read_stdout_to_queue_signals_eof_on_none_stream():
    q: "queue.Queue" = queue.Queue()
    bridge._read_stdout_to_queue(None, q)
    assert q.get_nowait() is None


def _make_test_api(monkeypatch):
    """Build a CalculusAPI shell with bridge state set up but no real worker."""
    api = bridge.CalculusAPI.__new__(bridge.CalculusAPI)
    api._render_worker = None
    api._render_worker_lock = threading.Lock()
    api._render_response_queue = queue.Queue()
    api._render_worker_stopping = threading.Event()
    api._render_worker_restart_failures = 0
    return api


def test_run_render_task_times_out_when_worker_silent(monkeypatch):
    monkeypatch.setattr(bridge, "_RENDER_TIMEOUT_SEC", 0.05)
    captured = _capture_logger(monkeypatch)

    api = _make_test_api(monkeypatch)

    written: list = []

    class _FakeStdin:
        def write(self, payload):
            written.append(payload)

        def flush(self):
            pass

    proc = SimpleNamespace(
        stdin=_FakeStdin(),
        returncode=None,
    )
    proc.poll = lambda: None
    proc.kill = lambda: setattr(proc, "returncode", -9)
    proc.wait = lambda timeout=None: None
    api._render_worker = proc

    out = api._run_render_task({"slide_title": "x"})

    assert out["success"] is False
    assert "timeout" in out["error"].lower()
    assert written, "payload should have been written before the timeout"
    assert any("timed out" in msg for level, msg in captured if level == "error")
    # Worker was killed and dropped so the next call would respawn.
    assert api._render_worker is None


def test_run_render_task_returns_error_when_worker_signals_eof(monkeypatch):
    monkeypatch.setattr(bridge, "_RENDER_TIMEOUT_SEC", 1.0)
    _capture_logger(monkeypatch)

    api = _make_test_api(monkeypatch)

    class _FakeStdin:
        def write(self, payload):
            pass

        def flush(self):
            pass

    proc = SimpleNamespace(
        stdin=_FakeStdin(),
        returncode=-1,
    )
    proc.poll = lambda: -1
    proc.kill = lambda: None
    proc.wait = lambda timeout=None: None
    api._render_worker = proc
    # Pre-stage the EOF sentinel that the stdout reader would push on worker exit
    # and bypass restart by keeping proc.poll alive at write time.
    proc.poll = lambda: None
    api._render_response_queue.put(None)

    out = api._run_render_task({"slide_title": "y"})
    assert out["success"] is False
    assert "exited" in out["error"].lower()


def test_run_render_task_surfaces_unavailable_when_restart_fails(monkeypatch):
    _capture_logger(monkeypatch)
    api = _make_test_api(monkeypatch)

    def _failed_restart():
        api._render_worker = None

    monkeypatch.setattr(api, "_start_render_worker_locked", _failed_restart)

    out = api._run_render_task({"slide_title": "z"})
    assert out["success"] is False
    assert out["error"] == "Render worker unavailable"


def test_capacity_test_slide_returns_capability_unavailable():
    api = bridge.CalculusAPI.__new__(bridge.CalculusAPI)
    out = json.loads(api.capacity_test_slide("hello"))
    assert out["success"] is False
    assert out["error"] == "capability_unavailable"
    assert "reason" in out


def test_capacity_metrics_only_returns_capability_unavailable():
    api = bridge.CalculusAPI.__new__(bridge.CalculusAPI)
    out = api._capacity_metrics_only("hello")
    assert out["success"] is False
    assert out["error"] == "capability_unavailable"


def test_run_capacity_worker_returns_capability_unavailable():
    api = bridge.CalculusAPI.__new__(bridge.CalculusAPI)
    out = api._run_capacity_worker("hello")
    assert out["success"] is False
    assert out["error"] == "capability_unavailable"
