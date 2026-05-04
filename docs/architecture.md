# Architecture

This document describes how Calculus Animator is wired together at runtime — the process model, IPC shape, module responsibilities, and lifecycle. It is the doc to read first when you want to understand or modify the system; the README focuses on what the app does for users.

## Process Model

The running app spans **three Python processes** plus the embedded WebView, which together form a strict hub-and-spoke topology with the PyWebView shell as the user-facing root.

```
┌──────────────────────────────────────────────────────────────────┐
│  Process A — PyWebView Shell  (run.py → window.py)               │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Embedded WebView (browser engine, OS-native)            │    │
│  │  Loads ui/index.html → ui/js/app.js + modules/*          │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Python side: api.bridge.CalculusAPI (exposed to JS as `pywebview.api`) │
│       │              │                                            │
│       │              └── HTTP ──► Process B (AI tutor backend)    │
│       └── stdin/stdout JSON ────► Process C (slide render worker) │
└──────────────────────────────────────────────────────────────────┘

Process B — FastAPI AI Tutor Backend       Process C — Pygame Render Worker
       (ai_tutor/main.py)                       (api/slide_render_worker.py)
       Bound to 127.0.0.1                       Persistent subprocess
       HTTP/JSON                                Line-delimited JSON over stdin/stdout
       JSON access logs with request_id         stderr drained to parent logger
```

- **Process A** owns the WebView and is the user-facing entrypoint. It instantiates `CalculusAPI` and registers it as the JavaScript-callable bridge. It also spawns and supervises Processes B and C.
- **Process B** is a FastAPI server providing AI tutoring (RAG + LLM provider routing + vision). It is bound to loopback only and has no external network surface.
- **Process C** is a long-lived pygame-based slide-render worker. The bridge talks to it via line-delimited JSON over stdin/stdout. There is at most one render worker; the bridge serializes calls with a render lock.

Workers other than slide-render (e.g., capacity-test) are spawned on demand and torn down per call rather than kept persistent.

## IPC Shapes

### Bridge ↔ Render Worker

- Transport: pipes (stdin write, stdout read, stderr read).
- Encoding: one JSON object per line in both directions.
- Reliability: stdout reads happen via a queue-fed reader thread with a configurable timeout (`CALC_ANIM_RENDER_TIMEOUT_SEC`, default 60s). On timeout the bridge kills the worker, restarts it on the next call, and returns a structured error to the caller.
- Stderr: drained continuously by `_drain_stream_to_logger` daemon thread into the project logger at WARNING level with a `[render-worker]` label. Pipe buffer can never fill.
- Crash detection: `_watchdog_loop` polls `proc.poll()` every `_WATCHDOG_INTERVAL_SEC` (default 2s); on crash it restarts the worker. Restart storms are bounded by `_MAX_CONSECUTIVE_RESTART_FAILURES` (default 3); once exhausted, subsequent calls return `capability_unavailable` instead of starting a restart loop.

### Bridge ↔ AI Tutor Backend

- Transport: HTTP over loopback (`127.0.0.1:<port>`).
- Encoding: JSON request/response.
- Middleware order (outer → inner): `RequestIdMiddleware` → `AccessLogMiddleware` → `CORSMiddleware` → `MaxBodySizeMiddleware` → app.
- Request IDs: `RequestIdMiddleware` honours an inbound `X-Request-Id` header (so the bridge can propagate its own correlation ID) or generates a UUID4 fresh. Always echoed in the response. The ID is bound to a `contextvars.ContextVar` so every `logger.*` call within the request automatically includes it.
- Errors: all exceptions flow through three exception handlers (`HTTPException`, `RequestValidationError`, `Exception`) and emit a structured envelope: `{"error": {"type", "message", "request_id"[, "details"]}}`. No traceback or stack-trace text leaks into HTTP response bodies.
- Outbound LLM calls: each provider call site validates the target URL against an allowlist before firing (SSRF protection).

### WebView ↔ Bridge

- Transport: PyWebView's native JS-to-Python binding (no network).
- API: methods on `CalculusAPI` are exposed under `pywebview.api.*` to the WebView JavaScript context.
- Concurrency: JavaScript calls into the bridge can interleave; the bridge serializes worker stdin via `_render_worker_lock`. Per-call queue instances prevent reader-thread sentinels from leaking across worker generations.

## Module Responsibilities

| Path | Responsibility |
|------|----------------|
| `run.py` | Canonical user-facing launcher. Drains backend `stderr` to the project logger, supervises the FastAPI subprocess, instantiates `CalculusAPI`, calls `webview.create_window`. Use `python run.py --help` / `--version` to inspect without launching. |
| `window.py` | PyWebView shell helper. Importable; not a separate user-facing entrypoint. |
| `scripts/build_release.py` | PyInstaller artifact builder. Release-only. Install build deps via `pip install -e .[build]`. |
| `scripts/smoke_test.py` | Three-check non-interactive verification (backend constructs, bridge probe, end-to-end render pipeline). Exit 0 on pass. |
| `api/bridge.py` | `CalculusAPI` — JS-callable methods, render-worker lifecycle, capacity probes. Owns the watchdog and stderr-drain machinery. |
| `api/slide_render_worker.py` | Pygame-based persistent render worker. JSON-line protocol on stdin/stdout. |
| `ai_tutor/main.py` | FastAPI app. Wires middleware, exception handlers, lifespan startup (calls `configure_logging()`), and route routers. |
| `ai_tutor/middleware.py` | `RequestIdMiddleware`, `MaxBodySizeMiddleware`, `AccessLogMiddleware`. |
| `ai_tutor/logging_config.py` | `request_id_var` ContextVar, `RequestIdFilter`, JSON formatter, `configure_logging()` (idempotent). |
| `ai_tutor/providers/router.py` | Multi-provider LLM dispatch (DeepSeek, Google, OpenAI, Anthropic, Ollama). SSRF allowlist + per-provider URL validation. |
| `ai_tutor/rag/` | Curriculum retrieval (ChromaDB-backed). Optional dependency; the package imports cleanly without `chromadb` installed. |
| `core/` | Symbolic math: parser, detector, extractor, solver, step generator, animation engine. SymPy under the hood. |
| `slide_renderer/` | Pygame slide rendering primitives (auxiliary package; not on the OSS POC critical path). |
| `ui/index.html`, `ui/js/app.js` | WebView entrypoint and main JS module. |
| `ui/js/modules/renderer.js` | Renderer module — math + slide rendering. Uses safe DOM APIs throughout; `katex` invoked with `trust: false`. Uses `_setSafe` / `_ensureChild` to prevent prototype-pollution writes. |
| `ui/vendor/katex/`, `ui/vendor/mathlive/` | Vendored math libraries (KaTeX 0.16.11, MathLive 0.101.0) for offline rendering. |

## Lifecycle

1. User runs `python run.py`.
2. `run.py` checks/installs missing runtime deps, then spawns Process B (FastAPI backend) as a subprocess. Backend `stderr` is drained into the project logger via a daemon reader thread.
3. `run.py` instantiates `CalculusAPI` (which spawns Process C — the render worker — lazily on first call).
4. PyWebView opens the desktop window pointing at `ui/index.html`.
5. The frontend's `app.js` calls `pywebview.api.boot(...)` (or equivalent) to wire bridge ↔ UI.
6. User flows: solve / render / tutor calls flow through the bridge into the appropriate process.
7. Shutdown: ctrl+C or window-close terminates Process A; the bridge's watchdog terminates Process C; FastAPI's lifespan shutdown handler drains in-flight requests on Process B.

## Configuration Surface

All runtime configuration is via environment variables (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `CALCANIM_MAX_REQUEST_BYTES` | 10485760 (10 MiB) | Maximum request body size accepted by the FastAPI backend. |
| `CALC_ANIM_RENDER_TIMEOUT_SEC` | 60 | Render worker `readline` timeout. |
| `_STARTUP_TIMEOUT_SEC` | 5 | Render worker startup timeout. |
| `_WATCHDOG_INTERVAL_SEC` | 2 | Watchdog poll interval. |
| `LLM_PROVIDER` | `deepseek` | Active LLM provider for the AI tutor. |
| `DEEPSEEK_API_KEY`, `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` | — | Provider API keys (whichever provider is active). |

## Threading and Concurrency Model

- **Process A** (PyWebView shell): main thread runs the WebView event loop. Daemon threads handle: (a) backend `stderr` drain, (b) render-worker `stderr` drain, (c) render-worker stdout queue feeder, (d) watchdog poll loop.
- **Process B** (FastAPI): default uvicorn event loop. Per-request `contextvars.ContextVar` carries the request ID through async call chains.
- **Process C** (render worker): single-threaded pygame loop, blocks on stdin between calls.

Cross-process state is intentionally minimal — there is no shared memory or shared filesystem state beyond the read-only `data/` curriculum and the read-only `ui/` assets.

## Why This Shape

- **PyWebView over Electron**: smaller distribution (~80MB vs ~200MB), single Python codebase, native OS integration without Chromium bundle.
- **Subprocess workers over threads**: pygame can hang or crash; isolation protects the main process. Memory is isolated from the renderer's leaks.
- **FastAPI bridge over direct PyWebView binding for AI tutor**: language-agnostic, future-proofing for web/mobile ports, async-native for concurrent solve+render+chat, OpenAPI documentation for free.
- **Loopback-only over real auth**: this is a single-user desktop app. The host machine is trusted; the network boundary is the loopback interface.
- **Vendored math libraries over CDN**: clients running offline (e.g., classrooms, restricted networks) need the app to work without network access.
