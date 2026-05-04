# Calculus Animator — Hugging Face Space (Docker SDK) image.
#
# Single-stage build: FastAPI process serves the static ``ui/`` bundle at
# ``/`` and the ``/api/*`` JSON shim that mirrors ``api.bridge.CalculusAPI``
# for the browser-side ``space_bridge.js``.
#
# Slide-render note: SDL2 runtime libs are installed below so a future
# ``pygame==…`` line drop-in to ``requirements.txt`` enables the slide
# render endpoints without rebuilding the OS layer. v1 ships without
# pygame; ``/api/render_learning_slide`` returns ModuleNotFoundError via
# the global error envelope until that line lands.

FROM python:3.11-slim AS base

# ── OS deps ──────────────────────────────────────────────────────────────────
# xvfb + libsdl2-* + fontconfig: pygame runtime support (headless rendering
# under SDL_VIDEODRIVER=dummy). Layered first so the Python install layer
# below stays cache-friendly across requirements.txt edits.
RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb \
        libsdl2-2.0-0 \
        libsdl2-image-2.0-0 \
        libsdl2-mixer-2.0-0 \
        libsdl2-ttf-2.0-0 \
        fontconfig \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Headless SDL: pygame opens a dummy framebuffer, never touches a GPU/X server.
ENV SDL_VIDEODRIVER=dummy \
    PYGAME_HIDE_SUPPORT_PROMPT=1 \
    XDG_RUNTIME_DIR=/tmp \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ── Python deps ──────────────────────────────────────────────────────────────
# Copy requirements first so the install layer caches across source edits.
# We intentionally skip ``requirements-ai.txt`` (chromadb + sentence-transformers
# are heavyweight and unused by the desktop core that the Space serves);
# adding them is a one-line ``-r requirements-ai.txt`` change in this RUN.
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# ── Source ───────────────────────────────────────────────────────────────────
# Copy the runtime trees the FastAPI app actually imports; release-only
# scripts and dev fixtures stay out of the image.
COPY ai_tutor/ ./ai_tutor/
COPY api/ ./api/
COPY core/ ./core/
COPY ui/ ./ui/
COPY slide_renderer/ ./slide_renderer/
COPY scripts/ ./scripts/
COPY data/ ./data/
# ``assets/`` (pygame fonts) is intentionally absent on this branch — HF's
# binary-file rule rejects ``.ttf`` files, and slide rendering is not the
# Space's primary surface. ``/api/render_learning_slide`` will surface a
# missing-font error via the structured error envelope; Solve and graph
# endpoints work without it. Restore via Git LFS if slide rendering is
# wanted on the Space.
# ``config.py`` lives at the project root and is imported by ``run.py`` and
# tests; keep it on the image so any module that walks ``sys.path[0]``
# resolves it the same way as on the host.
COPY config.py ./config.py

# ── Non-root runtime ─────────────────────────────────────────────────────────
# Hugging Face Spaces require the container to run as a non-root user (UID
# 1000 is the convention HF documents). Create the user, hand it ownership of
# /app, and switch.
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 7860

# ``--host 0.0.0.0`` is required for HF Spaces (host can only route to the
# container via the published port). Loopback-only binding lives on the
# desktop branch's ``run.py`` path; this image's threat model is the
# Space-managed reverse proxy in front of the container.
CMD ["uvicorn", "ai_tutor.main:app", "--host", "0.0.0.0", "--port", "7860"]
