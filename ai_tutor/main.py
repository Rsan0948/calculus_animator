"""FastAPI main entry point for AI Tutor.

ZDS-ID: TOOL-302 (Interface-Agnostic Core)
ZDS-ID: TOOL-1002 (Unified Entry Point Orchestrator)

Serves:
- Desktop app (PyWebView bridge)
- Direct API clients
- Future web frontend
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_tutor.config import get_settings
from ai_tutor.rag.concept_engine import get_concept_engine
from ai_tutor.routers import settings_router, tutor


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager."""
    # Startup
    settings = get_settings()
    
    # Validate settings
    issues = settings.validate()
    if issues:
        for _issue in issues:
            pass
    
    # Initialize concept engine if data exists
    engine = get_concept_engine()
    if engine.cards_path.exists():
        pass
    else:
        pass
    
    yield
    
    # Shutdown


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    get_settings()
    
    app = FastAPI(
        title="Calculus AI Tutor",
        description="Socratic tutoring with multi-modal context for Calculus Animator",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # CORS for desktop app and potential web frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, restrict this
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(tutor.router, prefix="/tutor", tags=["tutor"])
    app.include_router(settings_router.router, prefix="/settings", tags=["settings"])
    
    @app.get("/")
    async def root():
        return {
            "service": "Calculus AI Tutor",
            "version": "1.0.0",
            "zds_components": [
                "TOOL-102 (Doctrine RAG Stack)",
                "TOOL-305 (Intelligent Cloud Failover)",
                "TOOL-405 (Teacher-in-the-Loop)",
            ]
        }
    
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        settings = get_settings()
        engine = get_concept_engine()
        
        cards_count = len(engine.load_cards()) if engine.cards_path.exists() else 0
        
        return {
            "status": "healthy",
            "llm_provider": settings.llm_provider,
            "models_configured": bool(settings.fast_model or settings.get_model("fast")),
            "concept_cards": cards_count,
            "dense_retrieval": settings.dense_enabled,
            "rerank_enabled": settings.rerank_enabled,
        }
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    
    uvicorn.run(
        "ai_tutor.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info"
    )
