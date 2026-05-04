"""FastAPI main entry point for AI Tutor.

ZDS-ID: TOOL-302 (Interface-Agnostic Core)
ZDS-ID: TOOL-1002 (Unified Entry Point Orchestrator)

Serves:
- Desktop app (PyWebView bridge)
- Direct API clients
- Hugging Face Space (Docker SDK): same FastAPI process serves the
  ``ui/`` static bundle at ``/`` and the ``/api/*`` JSON shim that
  mirrors ``api.bridge.CalculusAPI`` for the browser-side
  ``space_bridge.js``.

This is a local desktop app: the backend binds to ``127.0.0.1`` only and
serves callers running on the same machine (the PyWebView shell or a
developer's localhost browser). There is intentionally no auth — loopback
binding is the perimeter. Hardening implemented here:

- Explicit loopback CORS origin list (no ``*``).
- Request body size limit (env-tunable) returning a structured 413.
- Global exception handlers emit a structured error envelope; raw
  tracebacks never leak into the response body.
- Per-request UUID4 correlation id propagated to every log line via a
  ContextVar.
- ``GET /health`` is a liveness probe (always 200 if the process is
  responsive); ``GET /ready`` is a readiness probe (200 once startup
  completes, 503 before).
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from ai_tutor.config import get_settings
from ai_tutor.logging_config import (
    REQUEST_ID_HEADER,
    configure_logging,
    request_id_var,
)
from ai_tutor.middleware import (
    AccessLogMiddleware,
    MaxBodySizeMiddleware,
    RequestIdMiddleware,
    get_max_request_bytes,
)
from ai_tutor.rag.concept_engine import get_concept_engine
from ai_tutor.routers import api_bridge, settings_router, tutor

logger = logging.getLogger(__name__)

# UI bundle lives at the project root next to ``ai_tutor/``. Resolve once at
# import time so the StaticFiles mount uses an absolute path regardless of
# the cwd uvicorn is launched from (matters for the Docker Space build).
_UI_DIR = (Path(__file__).resolve().parent.parent / "ui").resolve()


def _loopback_origins(port: int) -> list[str]:
    """Build the explicit CORS origin list for the desktop loopback shell."""
    return [
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
    ]


def _error_envelope(error_type: str, message: str, request_id: str) -> dict:
    """Standard error envelope. Tracebacks never appear here — they go to logs."""
    return {
        "error": {
            "type": error_type,
            "message": message,
            "request_id": request_id,
        }
    }


def _close_logger_handlers() -> None:
    """Flush + close every handler attached to the root and uvicorn loggers.

    Called from the lifespan shutdown phase so a SIGTERM / SIGINT exit
    doesn't truncate the last-line buffer or leave file descriptors open.
    """
    targets = [logging.getLogger(), logging.getLogger("uvicorn"),
               logging.getLogger("uvicorn.error"), logging.getLogger("uvicorn.access")]
    for lg in targets:
        for handler in list(lg.handlers):
            try:
                handler.flush()
                handler.close()
            except (OSError, ValueError) as exc:
                # Logger teardown is best-effort; never raise out of shutdown.
                logger.debug("handler close failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan: gate /ready, then drain on shutdown.

    Startup:
      1. Configure structured JSON logging.
      2. Validate settings.
      3. Touch the concept engine so its singleton is hot.
      4. Flip ``app.state.ready`` so /ready starts returning 200.

    Shutdown (uvicorn graceful path on SIGTERM / SIGINT — uvicorn stops
    accepting new connections and drains in-flight requests before this
    block runs):
      1. Flip ``app.state.ready`` so /ready returns 503 immediately.
      2. Log the shutdown.
      3. Close logger handlers.
    """
    # Startup
    configure_logging()
    settings = get_settings()

    issues = settings.validate()
    if issues:
        for issue in issues:
            logger.warning("settings validation issue: %s", issue)

    engine = get_concept_engine()
    if engine.cards_path.exists():
        logger.info("concept engine ready", extra={"cards_path": str(engine.cards_path)})
    else:
        logger.info(
            "concept engine has no card store yet",
            extra={"cards_path": str(engine.cards_path)},
        )

    app.state.ready = True
    logger.info("ai_tutor startup complete")

    yield

    # Shutdown
    app.state.ready = False
    logger.info("ai_tutor shutting down")
    _close_logger_handlers()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()
    configure_logging()

    app = FastAPI(
        title="Calculus AI Tutor",
        description="Socratic tutoring with multi-modal context for Calculus Animator",
        version="1.0.0",
        lifespan=lifespan
    )
    # Default to not-ready until the lifespan startup hook flips it. Tests
    # that bypass the startup hook (e.g. construct ``create_app()`` directly
    # without entering the lifespan context) can set this manually.
    app.state.ready = False

    # ── Middleware stack (registered innermost-first; Starlette wraps last
    # registered as outermost). Effective order from outer to inner:
    #   RequestId → AccessLog → CORS → MaxBodySize → app
    # RequestId outermost so the ContextVar is set before any other layer
    # logs or builds a 413 envelope.
    app.add_middleware(MaxBodySizeMiddleware, max_bytes=get_max_request_bytes())
    app.add_middleware(
        CORSMiddleware,
        # Local desktop app: only the PyWebView shell + loopback browser are
        # legitimate origins. Anything else is misconfiguration or attack.
        # In Space (Docker) mode the browser hits the same origin as the
        # backend, so CORS preflight isn't triggered for those requests.
        allow_origins=_loopback_origins(settings.port),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", REQUEST_ID_HEADER],
    )
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIdMiddleware)

    # ── Exception handlers: every error path produces the structured
    # envelope with a request_id. Tracebacks go to logs only.

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(request: Request, exc: StarletteHTTPException):
        rid = request_id_var.get()
        body = _error_envelope(exc.__class__.__name__, str(exc.detail), rid)
        return JSONResponse(
            content=body,
            status_code=exc.status_code,
            headers={REQUEST_ID_HEADER: rid},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        rid = request_id_var.get()
        body = _error_envelope("ValidationError", "Request validation failed", rid)
        body["error"]["details"] = exc.errors()
        return JSONResponse(
            content=body,
            status_code=422,
            headers={REQUEST_ID_HEADER: rid},
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception):
        rid = request_id_var.get()
        # Full traceback to the structured log; safe message to the response.
        logger.exception(
            "unhandled exception",
            extra={"path": request.url.path, "method": request.method},
        )
        body = _error_envelope(exc.__class__.__name__, "internal server error", rid)
        return JSONResponse(
            content=body,
            status_code=500,
            headers={REQUEST_ID_HEADER: rid},
        )

    # Routers (must be included before the catch-all StaticFiles mount so
    # ``/api/*`` / ``/tutor/*`` / ``/settings/*`` are matched as routes
    # rather than swallowed by the UI fallback).
    app.include_router(api_bridge.router, prefix="/api", tags=["api"])
    app.include_router(tutor.router, prefix="/tutor", tags=["tutor"])
    app.include_router(settings_router.router, prefix="/settings", tags=["settings"])

    @app.get("/health")
    async def health():
        """Liveness probe — always 200 if the process is responsive.

        Intentionally cheap: no DB hit, no provider check, no card load.
        Use ``/ready`` for the readiness signal (gated on startup
        completion).
        """
        return {"status": "healthy"}

    @app.get("/ready")
    async def ready(request: Request):
        """Readiness probe — 200 once lifespan startup has completed.

        Returns 503 between process boot and ``app.state.ready = True``,
        and again from the moment shutdown begins (the lifespan shutdown
        hook flips the flag back to False before draining handlers).
        """
        if getattr(request.app.state, "ready", False):
            return {"status": "ready"}
        return JSONResponse(
            content={"status": "not_ready"},
            status_code=503,
        )

    # Static UI bundle. ``html=True`` makes the mount serve ``index.html``
    # for directory requests (so ``GET /`` returns the desktop UI HTML in
    # Space mode). Mounted last so explicit routes above take priority.
    if _UI_DIR.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=str(_UI_DIR), html=True),
            name="ui",
        )
    else:
        logger.warning(
            "UI directory not found at %s — / will 404; expected for backend-only test runs",
            _UI_DIR,
        )

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    # Loopback-only by design. Even if settings.host is overridden elsewhere,
    # the host bound here is the perimeter of the local-desktop deployment.
    # The Space (Docker) build uses ``CMD ["uvicorn", "ai_tutor.main:app",
    # "--host", "0.0.0.0", ...]`` instead of this entry path.
    uvicorn.run(
        "ai_tutor.main:app",
        host="127.0.0.1",
        port=settings.port,
        reload=False,
        log_level="info",
    )
