"""Settings management router.

Handles provider configuration and API key management.
ZDS-ID: TOOL-903 (Automated Secrets Guardrail)
"""

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


@router.post("/provider")
async def update_provider(config: ProviderConfig):
    """Update provider configuration."""
    settings = get_settings()
    
    # Update provider
    settings.llm_provider = config.provider
    
    # Update models if specified
    if config.fast_model:
        settings.fast_model = config.fast_model
    if config.power_model:
        settings.power_model = config.power_model
    if config.vision_model:
        settings.vision_model = config.vision_model
    
    # Update API keys if provided (write to env for session)
    if config.openai_api_key:
        # In production, use secure keychain storage
        import os
        os.environ["OPENAI_API_KEY"] = config.openai_api_key
        settings.openai_api_key = config.openai_api_key
    
    if config.anthropic_api_key:
        import os
        os.environ["ANTHROPIC_API_KEY"] = config.anthropic_api_key
        settings.anthropic_api_key = config.anthropic_api_key
    
    if config.google_api_key:
        import os
        os.environ["GOOGLE_API_KEY"] = config.google_api_key
        settings.google_api_key = config.google_api_key
    
    if config.deepseek_api_key:
        import os
        os.environ["DEEPSEEK_API_KEY"] = config.deepseek_api_key
        settings.deepseek_api_key = config.deepseek_api_key
    
    # Validate
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
    from ai_tutor.services.ingest import ingest_curriculum
    
    try:
        result = ingest_curriculum()
        return {"status": "success", "details": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
