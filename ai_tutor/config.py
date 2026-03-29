"""Configuration management for AI Tutor.

ZDS-ID: TOOL-903 (Automated Secrets Guardrail)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TutorSettings:
    """AI Tutor configuration with secure API key handling."""
    
    # LLM Provider Configuration
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "local"))
    fast_model: str = field(default_factory=lambda: os.getenv("FAST_MODEL", ""))
    power_model: str = field(default_factory=lambda: os.getenv("POWER_MODEL", ""))
    vision_model: str = field(default_factory=lambda: os.getenv("VISION_MODEL", ""))
    
    # API Keys (loaded from env, never hardcoded)
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    google_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    deepseek_api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    
    # RAG Configuration
    vector_db_path: Path = field(default_factory=lambda: Path("data/vectors"))
    concept_cards_path: Path = field(default_factory=lambda: Path("data/concepts.jsonl"))
    concept_index_path: Path = field(default_factory=lambda: Path("data/concepts.db"))
    embed_model: str = "all-MiniLM-L6-v2"
    rerank_model: str = "BAAI/bge-reranker-base"
    dense_enabled: bool = True
    rerank_enabled: bool = True
    
    # Tutor Behavior
    max_context_cards: int = 3
    socratic_mode: bool = True  # If False, allows direct answers
    streaming_enabled: bool = True
    
    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    
    @property
    def absolute_vector_path(self) -> Path:
        """Resolve vector DB path relative to project root."""
        base = Path(__file__).parent.parent
        return (base / self.vector_db_path).resolve()
    
    def get_default_models(self) -> dict:
        """Get default models based on provider."""
        defaults = {
            "openai": {
                "fast": "gpt-4o-mini",
                "power": "gpt-4o",
                "vision": "gpt-4o"
            },
            "anthropic": {
                "fast": "claude-3-haiku-20240307",
                "power": "claude-3-5-sonnet-20240620",
                "vision": "claude-3-5-sonnet-20240620"
            },
            "google": {
                "fast": "gemini-1.5-flash",
                "power": "gemini-1.5-pro",
                "vision": "gemini-1.5-pro"
            },
            "deepseek": {
                "fast": "deepseek-chat",
                "power": "deepseek-reasoner",
                "vision": "deepseek-chat"  # No vision support yet
            },
            "local": {
                "fast": "mistral",
                "power": "llama3.2",
                "vision": ""  # Local vision models rare
            },
            "gemini_cli": {
                "fast": "gemini-2.0-flash",
                "power": "gemini-2.0-flash",
                "vision": "gemini-2.0-flash"
            }
        }
        return defaults.get(self.llm_provider, defaults["local"])
    
    def get_model(self, mode: str = "fast") -> str:
        """Get configured model for mode, with fallback to defaults."""
        configured = getattr(self, f"{mode}_model", "")
        if configured:
            return configured
        return self.get_default_models().get(mode, "mistral")
    
    def has_any_cloud_key(self) -> bool:
        """Check if any cloud provider is configured for failover."""
        return any([
            self.openai_api_key,
            self.anthropic_api_key,
            self.google_api_key,
            self.deepseek_api_key
        ])
    
    def validate(self) -> list[str]:
        """Validate configuration and return any issues."""
        issues = []
        from importlib.util import find_spec
        
        if self.llm_provider == "local":
            if find_spec("ollama") is None:
                issues.append("Ollama not installed. Run: pip install ollama")
        
        if self.llm_provider != "local" and not self.has_any_cloud_key():
            issues.append(f"Provider '{self.llm_provider}' selected but no API key configured")
        
        if self.dense_enabled:
            if find_spec("sentence_transformers") is None:
                issues.append("sentence-transformers not installed. Dense retrieval disabled.")
        
        return issues


# Global settings singleton
_settings: Optional[TutorSettings] = None


def get_settings() -> TutorSettings:
    """Get or create settings singleton."""
    global _settings
    if _settings is None:
        _settings = TutorSettings()
    return _settings


def reload_settings() -> TutorSettings:
    """Force reload settings from environment."""
    global _settings
    _settings = TutorSettings()
    return _settings
