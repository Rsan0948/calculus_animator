# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — Production-readiness arc (OSS POC)
- **Bridge worker reliability**: stderr-drain daemon thread, `readline()` timeout (default 60s, env-overridable via `CALC_ANIM_RENDER_TIMEOUT_SEC`), worker startup timeout (default 5s), proactive watchdog with bounded restart-storm protection (`api/bridge.py`)
- **Backend hardening**: loopback-only CORS, request-size limits via middleware (configurable `CALCANIM_MAX_REQUEST_BYTES`, default 10 MiB), structured error envelope (`{"error": {"type", "message", "request_id"[, "details"]}}`), JSON-formatted access logs with per-request UUID correlation, SSRF allowlist for outbound LLM provider calls (`ai_tutor/main.py`, `ai_tutor/middleware.py`, `ai_tutor/logging_config.py`)
- **Frontend safety**: XSS hardening in `ui/js/modules/renderer.js` (safe DOM APIs, `katex` invoked with `trust: false`), `Object.freeze(Object.prototype)` + `_setSafe` / `_ensureChild` helpers preventing prototype-pollution writes (`ui/js/app.js`, `ui/js/modules/renderer.js`)
- **Offline assets**: KaTeX 0.16.11 + MathLive 0.101.0 vendored under `ui/vendor/`; zero CDN script references in fetched URLs
- **Smoke test**: `scripts/smoke_test.py` verifies backend constructs, bridge probe, and end-to-end render pipeline
- **Health endpoints**: `/health` (lightweight liveness probe, no I/O) and `/ready` (503 until lifespan startup completes; flips back to 503 the moment shutdown begins) on the FastAPI backend
- **Graceful shutdown**: lifespan shutdown handler flips `ready=False` first, logs cleanly, closes/flushes logger handlers; SIGTERM and SIGINT exit cleanly with no orphan workers and no traceback noise
- **`run.py --help` / `--version`** short-circuit before launching the desktop window — usable on a fresh checkout without triggering the missing-deps prompt
- **`.env.example`** documenting every env var the app reads (active for vars that operators must set; commented for vars with sensible defaults)
- **JS lint pipeline**: ESLint 9 flat config (`eslint.config.js`) lints `ui/js/`, excludes `ui/vendor/`, runs on every PR via `npm run lint`
- **A11y baseline**: ARIA labels on landmarks, form controls, canvases, and icon-only buttons; `aria-live="polite"` on dynamic regions (step indicator, capacity stats, speed label); decorative glyphs marked `aria-hidden`
- **Test coverage gate**: CI enforces `--cov-fail-under=50` on `api + core + ai_tutor` (current 57.35%); local dev loop stays uninstrumented for speed
- **Pinned dependencies**: `requirements.txt`, `requirements-ai.txt`, `requirements-dev.txt` all `==`-pinned; `pyproject.toml` `[project.optional-dependencies]` extras (`ai_tutor`, `dev`, `build`) mirror them
- **PyInstaller pinned** in `[build]` extras; install via `pip install -e .[build]`
- **CI gates**: pip-audit on every PR (not cron-only), Bandit static security analysis, broadened mypy to `api core ai_tutor`, ruff F-class scanning the whole repo
- **SBOM** (CycloneDX) generated and attached to GitHub releases

### Changed
- Replaced deprecated `actions/create-release@v1` with `softprops/action-gh-release@v2` in the release workflow
- Capacity bridge methods now return honest `{"success": false, "error": "capability_unavailable", "reason": "..."}` instead of synthetic OK
- Frontend error-response handling adapted to the new structured error envelope shape
- `playwright` bumped from 1.47.0 to 1.49.0 for Python 3.13 compatibility (greenlet 3.1+ wheels)
- `run.py` is the canonical user-facing launcher; `window.py` is the PyWebView shell helper, `scripts/build_release.py` is release-only

### Fixed
- `re.sub(r"-+", "-").strip("-")` in `ai_tutor/rag/concept_engine.py` was missing its third positional argument (silently returned a partial method object); now correctly slugifies
- `core/parser.py` `parse('...')` returned Python's `Ellipsis` (via `sympify('...')→Ellipsis`), which has no `free_symbols`, raising `AttributeError` on the success branch; fix added a `hasattr(expr, "free_symbols")` guard so non-`Basic` singletons fall through to the failure envelope (caught by the hypothesis fuzz suite)
- 28 pre-existing mypy errors in `ai_tutor/` (var annotations, `chromadb.PersistentClient` typing, `NamedTemporaryFile` typing)
- 2 pre-existing F401 unused-import errors (`slide_renderer/engine.py`, `tests/test_bridge_contracts.py`)
- Backend subprocess `stderr` is now drained in `run.py` (was previously silenced via `subprocess.PIPE` with no reader, hiding startup errors)
- Path-traversal containment on temp-file `os.unlink` in Gemini-CLI helpers; bare `except: pass` patterns narrowed across `ai_tutor/`

### Security
- Loopback-only binding for the FastAPI backend (`host="127.0.0.1"`) — backend is unreachable from the network
- Request-size limits prevent memory-exhaustion DoS
- Global exception handlers ensure no traceback or stack-trace leakage in HTTP error responses
- SSRF allowlist enforced on every outbound LLM provider call

## [1.0.0] - 2024-03-20

### Added
- Initial release of Calculus Animator
- Auto-detection of 8 calculus operation types
  - Derivatives (including higher-order and partial)
  - Indefinite and definite integrals
  - Limits
  - Series expansions
  - Taylor/Maclaurin series
  - Ordinary differential equations
  - Simplification
- Step-by-step animation with live graphs
- PyWebView-based desktop application
- SymPy integration for symbolic computation
- Subprocess worker architecture for rendering isolation
- FastAPI bridge for Python-JavaScript communication
- Comprehensive test suite
  - Unit tests
  - Integration tests
  - End-to-end tests
  - Property-based fuzz tests
  - Snapshot regression tests
- Cross-platform packaging (Windows, macOS, Linux)
- ruff linting and mypy type checking
- GitHub Actions CI/CD

### Security
- Established security policy for vulnerability reporting

---

## Template for Future Releases

```
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes in existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Now removed features

### Fixed
- Bug fixes

### Security
- Security improvements
```
