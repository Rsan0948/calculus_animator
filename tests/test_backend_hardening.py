"""Focused backend-hardening tests for the FastAPI app and supporting modules.

Covers the five guarantees required by the backend hardening brief:

1. Oversized POST bodies return HTTP 413 with the structured error envelope.
2. Unhandled server errors return the structured envelope and **never** carry
   a raw traceback in the response body.
3. Every request emits a JSON access log line with a ``request_id`` that is
   consistent with logger.* records emitted within the request handler.
4. ``ai_tutor.providers.router._validate_provider_url`` rejects SSRF-shaped
   URLs (cloud metadata IP, http scheme, foreign hosts, cross-provider).
5. ``ai_tutor.rag.vector_store`` imports cleanly when ``chromadb`` is absent.
"""

from __future__ import annotations

import importlib
import json
import logging
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_tutor.logging_config import (
    REQUEST_ID_HEADER,
    JsonFormatter,
    RequestIdFilter,
    request_id_var,
)
from ai_tutor.main import create_app
from ai_tutor.middleware import MaxBodySizeMiddleware, RequestIdMiddleware
from ai_tutor.providers.router import _PROVIDER_HOSTS, _validate_provider_url


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def app() -> FastAPI:
    """Fresh app per test so route registrations / config state stay isolated.

    The ``/`` StaticFiles mount that ``create_app`` registers for the Docker
    Space build is removed here: tests below dynamically attach
    ``@app.get('/__test/*')`` routes after the fixture returns, and a
    catch-all mount registered earlier would 404 those paths before the
    test route ever runs.
    """
    fresh = create_app()
    fresh.routes[:] = [r for r in fresh.routes if getattr(r, "name", None) != "ui"]
    return fresh


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    # ``raise_server_exceptions=False`` lets us assert on the 500 response
    # body produced by our exception handler instead of pytest re-raising.
    return TestClient(app, raise_server_exceptions=False)


def _build_size_limited_app(max_bytes: int) -> TestClient:
    """Build a minimal ASGI app wrapped in MaxBodySizeMiddleware for size tests."""
    inner_app = FastAPI()

    @inner_app.post("/echo")
    async def _echo(payload: dict):  # pragma: no cover - body accepted means no 413
        return {"received": len(json.dumps(payload))}

    inner_app.add_middleware(MaxBodySizeMiddleware, max_bytes=max_bytes)
    inner_app.add_middleware(RequestIdMiddleware)
    return TestClient(inner_app, raise_server_exceptions=False)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Request size limit -> structured 413
# ─────────────────────────────────────────────────────────────────────────────


def test_oversized_post_returns_413_envelope() -> None:
    cap = 256
    tc = _build_size_limited_app(max_bytes=cap)

    payload = {"blob": "x" * (cap * 4)}
    resp = tc.post("/echo", json=payload)

    assert resp.status_code == 413, resp.text
    body = resp.json()
    assert "error" in body
    assert body["error"]["type"] == "RequestEntityTooLarge"
    assert "request_id" in body["error"]
    assert body["error"]["request_id"]
    # X-Request-Id echoed on the 413 too.
    assert resp.headers.get(REQUEST_ID_HEADER) == body["error"]["request_id"]


def test_under_limit_post_passes_through() -> None:
    tc = _build_size_limited_app(max_bytes=1024)
    resp = tc.post("/echo", json={"ok": True})
    assert resp.status_code == 200
    assert resp.json() == {"received": len(json.dumps({"ok": True}))}


# ─────────────────────────────────────────────────────────────────────────────
# 2. Error envelope without traceback
# ─────────────────────────────────────────────────────────────────────────────


def test_server_error_returns_envelope_without_traceback(
    app: FastAPI, client: TestClient
) -> None:
    @app.get("/__test/boom")
    async def _boom():
        raise RuntimeError("kaboom-secret-trace-info-/Users/private/path.py")

    resp = client.get("/__test/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["type"] == "RuntimeError"
    assert body["error"]["message"] == "internal server error"
    assert body["error"]["request_id"]

    # No traceback / source-path / exception-detail leaks in the response body.
    raw = resp.text
    assert "Traceback" not in raw
    assert "kaboom-secret-trace-info" not in raw
    assert "/Users/" not in raw


def test_http_exception_uses_envelope_shape(app: FastAPI, client: TestClient) -> None:
    from fastapi import HTTPException

    @app.get("/__test/forbid")
    async def _forbid():
        raise HTTPException(status_code=403, detail="nope")

    resp = client.get("/__test/forbid")
    assert resp.status_code == 403
    body = resp.json()
    assert body["error"]["type"] == "HTTPException"
    assert body["error"]["message"] == "nope"
    assert body["error"]["request_id"]


# ─────────────────────────────────────────────────────────────────────────────
# 3. Request-ID propagation in logs
# ─────────────────────────────────────────────────────────────────────────────


class _ListHandler(logging.Handler):
    """Test handler that records every formatted record for inspection."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_request_id_consistent_across_logger_calls(
    app: FastAPI, client: TestClient
) -> None:
    inner_logger = logging.getLogger("ai_tutor.test_handler")

    @app.get("/__test/log")
    async def _log_route():
        inner_logger.info("inside-handler-line-A")
        inner_logger.info("inside-handler-line-B")
        return {"ok": True}

    handler = _ListHandler()
    handler.setLevel(logging.INFO)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.addHandler(handler)
    try:
        resp = client.get("/__test/log")
    finally:
        root.removeHandler(handler)

    assert resp.status_code == 200
    rid = resp.headers.get(REQUEST_ID_HEADER)
    assert rid

    # Every record emitted within the request must carry the same request_id.
    inside_records = [
        r for r in handler.records
        if r.name in ("ai_tutor.test_handler", "ai_tutor.access")
        and getattr(r, "request_id", "-") != "-"
    ]
    assert inside_records, "expected request-scoped log records"
    rid_values = {getattr(r, "request_id") for r in inside_records}
    assert rid_values == {rid}, (
        f"request_id mismatch across log lines: {rid_values}, expected {{{rid}}}"
    )

    # And the access log line in particular has the structured fields.
    access_records = [r for r in inside_records if r.name == "ai_tutor.access"]
    assert access_records, "AccessLogMiddleware did not emit"
    access = access_records[-1]
    assert getattr(access, "method") == "GET"
    assert getattr(access, "path") == "/__test/log"
    assert getattr(access, "status_code") == 200


# ─────────────────────────────────────────────────────────────────────────────
# 4. SSRF allowlist
# ─────────────────────────────────────────────────────────────────────────────


# Sanity: the allowlist still describes the four canonical providers.
@pytest.mark.parametrize("provider", ["openai", "anthropic", "google", "deepseek"])
def test_each_provider_has_allowlist_entry(provider: str) -> None:
    assert provider in _PROVIDER_HOSTS
    assert _PROVIDER_HOSTS[provider], f"empty allowlist for {provider}"


@pytest.mark.parametrize(
    "provider, good_url",
    [
        ("openai", "https://api.openai.com/v1/chat/completions"),
        ("anthropic", "https://api.anthropic.com/v1/messages"),
        ("google", "https://generativelanguage.googleapis.com/v1beta/models/x:generateContent"),
        ("deepseek", "https://api.deepseek.com/chat/completions"),
    ],
)
def test_validator_accepts_known_provider_url(provider: str, good_url: str) -> None:
    assert _validate_provider_url(good_url, provider) == good_url


@pytest.mark.parametrize(
    "bad_url, reason",
    [
        ("http://169.254.169.254/latest/meta-data/", "cloud metadata IP via http"),
        ("https://169.254.169.254/latest/meta-data/", "cloud metadata IP via https"),
        ("https://attacker.example.com/v1/chat/completions", "foreign host"),
        ("file:///etc/passwd", "non-http scheme"),
        ("http://api.openai.com/v1/chat/completions", "http scheme on real host"),
    ],
)
@pytest.mark.parametrize("provider", ["openai", "anthropic", "google", "deepseek"])
def test_validator_rejects_ssrf_shaped_urls(
    bad_url: str, reason: str, provider: str
) -> None:
    with pytest.raises(ValueError):
        _validate_provider_url(bad_url, provider)


def test_validator_rejects_cross_provider_url() -> None:
    # OpenAI URL submitted as anthropic must fail.
    with pytest.raises(ValueError):
        _validate_provider_url(
            "https://api.openai.com/v1/chat/completions", "anthropic"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 5. vector_store imports without chromadb
# ─────────────────────────────────────────────────────────────────────────────


def test_vector_store_imports_without_chromadb(monkeypatch: pytest.MonkeyPatch) -> None:
    # Setting sys.modules entries to None makes the ``import`` statement raise
    # ImportError as if the package were not installed. The vector_store
    # try/except block must absorb that and keep ``CHROMA_AVAILABLE = False``.
    monkeypatch.setitem(sys.modules, "chromadb", None)
    monkeypatch.setitem(sys.modules, "chromadb.config", None)

    # Drop and re-import so the module-level try/except runs in this test
    # under the simulated "no chromadb" condition.
    monkeypatch.delitem(sys.modules, "ai_tutor.rag.vector_store", raising=False)

    module = importlib.import_module("ai_tutor.rag.vector_store")
    assert module.CHROMA_AVAILABLE is False
    # Calling the API path that needs chromadb should fail clearly, not
    # NameError on the type annotation.
    store = module.VectorStore.__new__(module.VectorStore)
    with pytest.raises(RuntimeError, match="ChromaDB not installed"):
        store._get_client()


# ─────────────────────────────────────────────────────────────────────────────
# 6. Loopback-only CORS
# ─────────────────────────────────────────────────────────────────────────────


def test_cors_allowlist_excludes_wildcard(app: FastAPI) -> None:
    cors_layers = [m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"]
    assert cors_layers, "CORSMiddleware not registered"
    # Starlette stores middleware constructor kwargs on the layer.
    options = cors_layers[0].kwargs
    origins = options.get("allow_origins") or []
    assert "*" not in origins, f"wildcard origin still present: {origins}"
    assert any(o.startswith("http://127.0.0.1") for o in origins)
    assert any(o.startswith("http://localhost") for o in origins)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Liveness / readiness probes
# ─────────────────────────────────────────────────────────────────────────────


def test_health_probe_is_lightweight(app: FastAPI) -> None:
    """``GET /health`` returns 200 with the minimal liveness envelope.

    Construct the client without entering the lifespan context manager —
    /health must be 200 even before lifespan startup completes.
    """
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


def test_ready_probe_503_before_startup(app: FastAPI) -> None:
    """``GET /ready`` returns 503 before the lifespan startup hook flips state."""
    client = TestClient(app, raise_server_exceptions=False)
    # No ``with`` context: the lifespan startup hook hasn't run yet, so
    # ``app.state.ready`` is still False.
    assert getattr(app.state, "ready", False) is False
    resp = client.get("/ready")
    assert resp.status_code == 503
    assert resp.json() == {"status": "not_ready"}


def test_ready_probe_200_after_startup(app: FastAPI) -> None:
    """``GET /ready`` returns 200 once the lifespan startup hook completes."""
    # ``with TestClient(...)`` triggers lifespan startup + teardown.
    with TestClient(app, raise_server_exceptions=False) as client:
        assert app.state.ready is True
        resp = client.get("/ready")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ready"}
    # After teardown the lifespan shutdown hook flips it back.
    assert app.state.ready is False


# Reset request_id_var after tests touch it via TestClient — defence-in-depth
# in case future tests leak context.
@pytest.fixture(autouse=True)
def _reset_request_id() -> None:
    token = request_id_var.set("-")
    try:
        yield
    finally:
        request_id_var.reset(token)
