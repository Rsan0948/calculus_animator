"""Settings management router.

Handles provider configuration and API key management.
ZDS-ID: TOOL-903 (Automated Secrets Guardrail)
"""

import threading
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai_tutor.config import get_settings
from ai_tutor.providers.router import (
    gemini_cli_available,
    get_gemini_cli_path,
    list_local_models,
    models_configured,
)

router = APIRouter()

# Guards the shared settings singleton against concurrent POST /provider
# requests that would otherwise interleave their field-by-field mutations.
_settings_lock = threading.Lock()


class ProviderConfig(BaseModel):
    """Provider configuration request/response."""
    provider: str = Field(..., description="LLM provider: local, openai, anthropic, google, deepseek")
    fast_model: str = Field("", description="Fast/cheap model for simple queries")
    power_model: str = Field("", description="Powerful model for complex reasoning")
    vision_model: str = Field("", description="Vision-capable model for screenshots")
    
    # API keys (only sent from client on update, never returned)
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(None, description="Anthropic API key")
    google_api_key: Optional[str] = Field(None, description="Google API key")
    deepseek_api_key: Optional[str] = Field(None, description="DeepSeek API key")


class SettingsResponse(BaseModel):
    """Safe settings response (no API keys)."""
    provider: str
    fast_model: str
    power_model: str
    vision_model: str
    dense_enabled: bool
    rerank_enabled: bool
    max_context_cards: int
    socratic_mode: bool
    streaming_enabled: bool
    
    # Status
    models_configured: bool
    local_models_available: list
    gemini_cli_available: bool
    gemini_cli_path: Optional[str] = None


@router.get("/", response_model=SettingsResponse)
async def get_current_settings():
    """Get current settings (safe version, no API keys)."""
    settings = get_settings()
    
    return SettingsResponse(
        provider=settings.llm_provider,
        fast_model=settings.get_model("fast"),
        power_model=settings.get_model("power"),
        vision_model=settings.get_model("vision") if settings.vision_model else "",
        dense_enabled=settings.dense_enabled,
        rerank_enabled=settings.rerank_enabled,
        max_context_cards=settings.max_context_cards,
        socratic_mode=settings.socratic_mode,
        streaming_enabled=settings.streaming_enabled,
        models_configured=models_configured(),
        local_models_available=list_local_models(),
        gemini_cli_available=gemini_cli_available(),
        gemini_cli_path=get_gemini_cli_path()
    )


_KNOWN_PROVIDERS = {"local", "gemini_cli", "openai", "anthropic", "google", "deepseek"}


@router.post("/provider")
async def update_provider(config: ProviderConfig):
    """Update provider configuration."""
    settings = get_settings()

    # Reject unknown providers BEFORE mutating the shared settings
    # singleton — an arbitrary string here would otherwise flow into
    # get_model()/provider dispatch and leave the process half-configured.
    if config.provider not in _KNOWN_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider '{config.provider}'. Valid: {sorted(_KNOWN_PROVIDERS)}",
        )

    # All mutations below touch the shared settings singleton; the lock
    # prevents two concurrent POST /provider requests from interleaving
    # their writes and leaving the process in a mixed state.
    with _settings_lock:
        # Update provider
        settings.llm_provider = config.provider

        # Update models if specified
        if config.fast_model:
            settings.fast_model = config.fast_model
        if config.power_model:
            settings.power_model = config.power_model
        if config.vision_model:
            settings.vision_model = config.vision_model

        # Update API keys if provided.
        # Keys are stored ONLY on the in-memory settings singleton.
        # They are NOT written to os.environ: this is a local single-user
        # app, and provider clients must read the key from the settings
        # object explicitly (e.g. settings.openai_api_key) rather than
        # relying on an environment variable.  This avoids leaking keys
        # into child processes (Ollama CLI, ingest subprocesses) and
        # /proc/<pid>/environ.
        if config.openai_api_key:
            settings.openai_api_key = config.openai_api_key

        if config.anthropic_api_key:
            settings.anthropic_api_key = config.anthropic_api_key

        if config.google_api_key:
            settings.google_api_key = config.google_api_key

        if config.deepseek_api_key:
            settings.deepseek_api_key = config.deepseek_api_key

    # Validate (outside the lock: validate() is read-only and should not
    # hold the write lock while potentially doing I/O).
    issues = settings.validate()
    if issues:
        raise HTTPException(status_code=400, detail={"issues": issues})
    
    return {"status": "updated", "provider": config.provider}


@router.get("/models/defaults")
async def get_default_models():
    """Get default models for each provider."""
    settings = get_settings()
    return settings.get_default_models()


@router.get("/models/local")
async def get_local_models():
    """List available local Ollama models."""
    return {"models": list_local_models()}


@router.post("/rag/rebuild")
async def rebuild_rag_index():
    """Trigger RAG index rebuild from curriculum."""
    import asyncio

    from ai_tutor.services.ingest import ingest_curriculum

    try:
        # Off the event loop: re-embeds every card and rebuilds Chroma +
        # SQLite FTS — running it inline froze all other requests.
        result = await asyncio.to_thread(ingest_curriculum)
        return {"status": "success", "details": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
