"""Tests for the formalization LLM client helpers."""

import pytest

from ingestion.formalization import llm_client


def test_call_formalizer_llm_prefers_gemini_cli(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "gemini_cli_available", lambda: True)
    monkeypatch.setattr(llm_client, "google_api_available", lambda: True)
    monkeypatch.setattr(
        llm_client,
        "_call_gemini_cli",
        lambda prompt, model, system=None: "cli-response",
    )

    response = llm_client.call_formalizer_llm("prompt", "gemini-1.5-pro", "system")

    assert response == "cli-response"


def test_call_formalizer_llm_falls_back_to_google_api(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "gemini_cli_available", lambda: False)
    monkeypatch.setattr(llm_client, "google_api_available", lambda: True)
    monkeypatch.setattr(
        llm_client,
        "_call_google_api",
        lambda prompt, model, system=None: "api-response",
    )

    response = llm_client.call_formalizer_llm("prompt", "gemini-1.5-pro", "system")

    assert response == "api-response"


def test_call_formalizer_llm_raises_when_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "gemini_cli_available", lambda: False)
    monkeypatch.setattr(llm_client, "google_api_available", lambda: False)

    with pytest.raises(RuntimeError, match="No formalization LLM configured"):
        llm_client.call_formalizer_llm("prompt", "gemini-1.5-pro")
