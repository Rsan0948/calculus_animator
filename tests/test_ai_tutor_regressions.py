"""Regression tests for the deep-review fixes to the AI tutor backend.

Pins the previously-broken behaviors:

1. ``generate_async`` dispatches on the configured provider (was hardcoded
   to DeepSeek regardless of ``LLM_PROVIDER``).
2. ``_attempt_cloud_failover`` is a plain function again — the old version
   contained a ``yield`` so non-streaming failover returned an empty
   generator object instead of the response string. Failover must also use
   the *target* provider's default model, not the configured (failed)
   provider's model name.
3. Streaming provider calls surface HTTP errors instead of yielding an
   empty stream; the Gemini error message must not echo the API key.
4. The route preflight returns 503 for local/gemini_cli providers whose
   runtime dependency is missing (previously the error fired inside the
   SSE generator, after the 200 headers).
5. ``/settings/provider`` rejects unknown provider names before mutating
   the shared settings singleton.
6. ConceptEngine.search: operation→topic alias mapping makes the topic
   boost live again; the trigger boost is bounded to one per card; and
   ``load_cards`` caches by file mtime.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import ai_tutor.providers.router as provider_router
import ai_tutor.routers.tutor as tutor_routes
from ai_tutor.config import get_settings
from ai_tutor.main import create_app
from ai_tutor.rag.concept_engine import (
    _OPERATION_TOPIC_ALIASES,
    ConceptCard,
    ConceptEngine,
)

MESSAGES = [{"role": "user", "content": "hi"}]


@pytest.fixture
def settings(monkeypatch):
    """The shared settings singleton with all keys cleared.

    monkeypatch.setattr restores every mutated attribute afterwards, so
    tests can reconfigure the singleton freely.
    """
    s = get_settings()
    for attr in ("openai_api_key", "anthropic_api_key", "google_api_key", "deepseek_api_key"):
        monkeypatch.setattr(s, attr, "")
    monkeypatch.setattr(s, "fast_model", "")
    monkeypatch.setattr(s, "power_model", "")
    monkeypatch.setattr(s, "llm_provider", "local")
    return s


# ─────────────────────────────────────────────────────────────────────────────
# 1. generate_async provider dispatch
# ─────────────────────────────────────────────────────────────────────────────


def test_generate_async_uses_configured_provider(monkeypatch, settings):
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "key-a")
    captured = {}

    async def fake_anthropic(messages, model, api_key, system=None):
        captured["model"] = model
        captured["api_key"] = api_key
        return "anthropic says hi"

    monkeypatch.setattr(provider_router, "_call_anthropic", fake_anthropic)
    out = asyncio.run(provider_router.generate_async("hello", mode="fast"))
    assert out == "anthropic says hi"
    # Model must be Anthropic's default for the mode — not a DeepSeek model.
    assert captured["model"] == settings.get_default_models("anthropic")["fast"]
    assert captured["api_key"] == "key-a"


def test_generate_async_missing_key_raises_for_configured_provider(monkeypatch, settings):
    monkeypatch.setattr(settings, "llm_provider", "openai")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        asyncio.run(provider_router.generate_async("hello"))


def test_generate_async_local_without_ollama_raises(monkeypatch, settings):
    monkeypatch.setattr(settings, "llm_provider", "local")
    monkeypatch.setattr(provider_router, "OLLAMA_AVAILABLE", False)
    with pytest.raises(RuntimeError, match="Ollama"):
        asyncio.run(provider_router.generate_async("hello"))


# ─────────────────────────────────────────────────────────────────────────────
# 2. Cloud failover: plain string return + target-provider model
# ─────────────────────────────────────────────────────────────────────────────


def test_failover_nonstreaming_returns_string_not_generator(monkeypatch, settings):
    monkeypatch.setattr(settings, "llm_provider", "local")
    monkeypatch.setattr(settings, "openai_api_key", "key-o")
    captured = {}

    async def fake_openai(messages, model, api_key, vision=False):
        captured["model"] = model
        return "cloud says hi"

    monkeypatch.setattr(provider_router, "_call_openai", fake_openai)
    out = provider_router._attempt_cloud_failover(MESSAGES, "fast", stream=False)
    assert out == "cloud says hi"  # a generator object would fail this
    # Must use OpenAI's default model, not the local provider's ("mistral").
    assert captured["model"] == settings.get_default_models("openai")["fast"]


def test_failover_streaming_yields_chunks_and_closes_loop(monkeypatch, settings):
    monkeypatch.setattr(settings, "llm_provider", "local")
    monkeypatch.setattr(settings, "openai_api_key", "key-o")

    async def fake_openai_stream(messages, model, api_key):
        for chunk in ("a", "b", "c"):
            yield chunk

    monkeypatch.setattr(provider_router, "_call_openai_stream", fake_openai_stream)
    gen = provider_router._attempt_cloud_failover(MESSAGES, "fast", stream=True)
    assert list(gen) == ["a", "b", "c"]


def test_failover_tries_next_provider_on_error(monkeypatch, settings):
    monkeypatch.setattr(settings, "llm_provider", "local")
    monkeypatch.setattr(settings, "openai_api_key", "key-o")
    monkeypatch.setattr(settings, "anthropic_api_key", "key-a")

    async def broken_openai(messages, model, api_key, vision=False):
        raise RuntimeError("openai down")

    async def fake_anthropic(messages, model, api_key, system=None):
        return "anthropic fallback"

    monkeypatch.setattr(provider_router, "_call_openai", broken_openai)
    monkeypatch.setattr(provider_router, "_call_anthropic", fake_anthropic)
    out = provider_router._attempt_cloud_failover(MESSAGES, "fast", stream=False)
    assert out == "anthropic fallback"


def test_failover_all_providers_broken_raises_with_details(monkeypatch, settings):
    monkeypatch.setattr(settings, "llm_provider", "local")
    monkeypatch.setattr(settings, "openai_api_key", "key-o")

    async def broken_openai(messages, model, api_key, vision=False):
        raise RuntimeError("openai down")

    monkeypatch.setattr(provider_router, "_call_openai", broken_openai)
    with pytest.raises(RuntimeError, match="openai down"):
        provider_router._attempt_cloud_failover(MESSAGES, "fast", stream=False)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Streaming providers surface HTTP errors
# ─────────────────────────────────────────────────────────────────────────────


def _mock_async_client(monkeypatch, status_code: int, body: dict):
    """Route every AsyncClient request through a canned-response transport."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=body)

    real_client = httpx.AsyncClient

    def fake_client(*args, **kwargs):
        return real_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(provider_router.httpx, "AsyncClient", fake_client)


async def _drain(agen):
    return [chunk async for chunk in agen]


def test_openai_stream_raises_on_auth_error(monkeypatch):
    _mock_async_client(monkeypatch, 401, {"error": "bad key"})
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(_drain(provider_router._call_openai_stream(MESSAGES, "gpt-4o-mini", "sk-bad")))


def test_anthropic_stream_raises_on_auth_error(monkeypatch):
    _mock_async_client(monkeypatch, 401, {"error": "bad key"})
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(
            _drain(provider_router._call_anthropic_stream(MESSAGES, "claude-3-haiku-20240307", "sk-bad"))
        )


def test_google_stream_error_is_sanitized(monkeypatch):
    # The Gemini request URL carries the API key; the raised error must not.
    _mock_async_client(monkeypatch, 403, {"error": "quota"})
    with pytest.raises(RuntimeError) as excinfo:
        asyncio.run(
            _drain(provider_router._call_google_stream(MESSAGES, "gemini-1.5-flash", "SECRET-KEY-123"))
        )
    assert "SECRET-KEY-123" not in str(excinfo.value)
    assert "status=403" in str(excinfo.value)


def test_openai_stream_still_parses_success(monkeypatch):
    sse_body = (
        'data: {"choices":[{"delta":{"content":"hel"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n'
        "data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=sse_body, headers={"content-type": "text/event-stream"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        provider_router.httpx,
        "AsyncClient",
        lambda *a, **kw: real_client(transport=httpx.MockTransport(handler)),
    )
    chunks = asyncio.run(_drain(provider_router._call_openai_stream(MESSAGES, "gpt-4o-mini", "sk")))
    assert chunks == ["hel", "lo"]


# ─────────────────────────────────────────────────────────────────────────────
# 4. Route preflight covers local/gemini_cli availability
# ─────────────────────────────────────────────────────────────────────────────


def test_preflight_local_without_ollama_is_503(monkeypatch, settings):
    monkeypatch.setattr(settings, "llm_provider", "local")
    monkeypatch.setattr(provider_router, "OLLAMA_AVAILABLE", False)
    with pytest.raises(HTTPException) as excinfo:
        tutor_routes._validate_provider_or_raise()
    assert excinfo.value.status_code == 503
    assert "Ollama" in excinfo.value.detail


def test_preflight_gemini_cli_missing_is_503(monkeypatch, settings):
    monkeypatch.setattr(settings, "llm_provider", "gemini_cli")
    monkeypatch.setattr(provider_router, "GEMINI_CLI_PATH", None)
    with pytest.raises(HTTPException) as excinfo:
        tutor_routes._validate_provider_or_raise()
    assert excinfo.value.status_code == 503


def test_preflight_local_with_ollama_passes(monkeypatch, settings):
    monkeypatch.setattr(settings, "llm_provider", "local")
    monkeypatch.setattr(provider_router, "OLLAMA_AVAILABLE", True)
    tutor_routes._validate_provider_or_raise()  # must not raise


def test_preflight_cloud_missing_key_is_503(monkeypatch, settings):
    monkeypatch.setattr(settings, "llm_provider", "openai")
    with pytest.raises(HTTPException) as excinfo:
        tutor_routes._validate_provider_or_raise()
    assert excinfo.value.status_code == 503


def test_chat_stream_route_returns_503_not_dead_sse(monkeypatch, settings):
    monkeypatch.setattr(settings, "llm_provider", "local")
    monkeypatch.setattr(provider_router, "OLLAMA_AVAILABLE", False)
    with TestClient(create_app()) as client:
        resp = client.post(
            "/tutor/chat/stream",
            json={
                "message": "help",
                "solver_state": {"expression": "x^2", "operation": "derivative"},
            },
        )
    assert resp.status_code == 503
    # The app wraps HTTPException in its structured error envelope; assert
    # on the serialized body rather than FastAPI's default `detail` shape.
    assert "Ollama" in json.dumps(resp.json())


# ─────────────────────────────────────────────────────────────────────────────
# 5. Settings route validates provider names
# ─────────────────────────────────────────────────────────────────────────────


def test_update_provider_rejects_unknown_provider(settings):
    with TestClient(create_app()) as client:
        before = settings.llm_provider
        resp = client.post("/settings/provider", json={"provider": "not-a-provider"})
        assert resp.status_code == 400
        assert "Unknown provider" in json.dumps(resp.json())
        assert settings.llm_provider == before, "singleton must not be mutated on reject"


# ─────────────────────────────────────────────────────────────────────────────
# 6. ConceptEngine scoring and caching
# ─────────────────────────────────────────────────────────────────────────────


def _card(card_id: str, topic: str, triggers: list[str]) -> ConceptCard:
    return ConceptCard(
        card_id=card_id,
        concept_name=card_id,
        topic=topic,
        subtopics=[],
        tags=[],
        question_triggers=triggers,
        core_formula="",
        when_to_use="",
        failure_modes=[],
        worked_example="",
        body="body",
        source_file="test",
        token_count=1,
    )


class _FakeVectorStore:
    def __init__(self, results):
        self._results = results

    def search(self, collection, query, n_results=9):
        return self._results


def _engine_with(monkeypatch, cards, vector_results) -> ConceptEngine:
    engine = ConceptEngine()
    monkeypatch.setattr(engine, "load_cards", lambda: cards)
    engine.vector_store = _FakeVectorStore(vector_results)
    return engine


def test_operation_topic_alias_map_covers_solver_operations():
    # SolverState.operation values that have a card-topic counterpart.
    assert _OPERATION_TOPIC_ALIASES["derivative"] == "derivatives"
    assert _OPERATION_TOPIC_ALIASES["integral"] == "integrals"
    assert _OPERATION_TOPIC_ALIASES["limit"] == "limits"
    assert _OPERATION_TOPIC_ALIASES["ode"] == "differential_equations"


def test_topic_boost_fires_for_solver_operation_values(monkeypatch):
    cards = [_card("on-topic", "derivatives", []), _card("off-topic", "series", [])]
    # Identical vector scores: only the topic boost can separate them.
    results = [
        {"id": "off-topic", "score": 0.5},
        {"id": "on-topic", "score": 0.5},
    ]
    engine = _engine_with(monkeypatch, cards, results)
    out = engine.search("explain this", topic="derivative", max_cards=2, use_rerank=False)
    assert [c.card_id for c in out] == ["on-topic", "off-topic"]


def test_trigger_boost_is_bounded_to_one_per_card(monkeypatch):
    # many-triggers: 5 matching triggers, lower vector score.
    # one-trigger: 1 matching trigger, higher vector score.
    # Old behavior: many-triggers gets +0.75 and drowns the vector term.
    cards = [
        _card("many-triggers", "general", ["derivative help"] * 5),
        _card("one-trigger", "general", ["derivative help"]),
    ]
    results = [
        {"id": "many-triggers", "score": 0.50},
        {"id": "one-trigger", "score": 0.60},
    ]
    engine = _engine_with(monkeypatch, cards, results)
    out = engine.search("derivative of x", topic=None, max_cards=2, use_rerank=False)
    assert [c.card_id for c in out] == ["one-trigger", "many-triggers"]


def test_trigger_boost_ignores_short_words(monkeypatch):
    # "of"/"x" are <=2 chars and must not trigger a substring boost.
    cards = [
        _card("short-word-bait", "general", ["profound explanation"]),  # contains "of"
        _card("clean", "general", ["unrelated"]),
    ]
    results = [
        {"id": "clean", "score": 0.55},
        {"id": "short-word-bait", "score": 0.50},
    ]
    engine = _engine_with(monkeypatch, cards, results)
    out = engine.search("of x", topic=None, max_cards=2, use_rerank=False)
    assert out[0].card_id == "clean"


def test_load_cards_caches_by_mtime(tmp_path, monkeypatch):
    cards_file = tmp_path / "concepts.jsonl"
    card = _card("c1", "derivatives", [])
    from dataclasses import asdict

    cards_file.write_text(json.dumps(asdict(card)) + "\n", encoding="utf-8")

    engine = ConceptEngine(cards_path=cards_file, index_path=tmp_path / "concepts.db")
    # The path-traversal guard requires cards under the project root; the
    # test file lives in tmp, so re-root the guard there.
    monkeypatch.setattr(engine, "_project_root", tmp_path)

    first = engine.load_cards()
    assert [c.card_id for c in first] == ["c1"]
    # Same mtime → identical cached object, no re-parse.
    assert engine.load_cards() is first

    # Rewrite with a different card and a bumped mtime → cache invalidates.
    card2 = _card("c2", "integrals", [])
    cards_file.write_text(json.dumps(asdict(card2)) + "\n", encoding="utf-8")
    import os

    stat = cards_file.stat()
    os.utime(cards_file, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    second = engine.load_cards()
    assert [c.card_id for c in second] == ["c2"]
