"""LLM Provider Router with Intelligent Cloud Failover.

ZDS-ID: TOOL-305 (Intelligent Cloud Failover)
ZDS-ID: TOOL-302 (Interface-Agnostic Core)
"""

from .router import generate, generate_stream, generate_vision, models_configured

__all__ = ["generate", "generate_stream", "generate_vision", "models_configured"]
