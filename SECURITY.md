# Security Policy

## Supported Versions

The following versions of Calculus Animator are currently supported with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please follow these steps:

### Please DO NOT

- **Do not** open a public issue for security vulnerabilities
- **Do not** discuss the vulnerability in public forums or chat
- **Do not** submit a pull request with the fix (until coordinated)

### Please DO

1. **Report privately** via GitHub Security Advisories:
   - Go to: https://github.com/Rsan0948/calculus_animator/security/advisories/new
   - Or email: rubmatsan2001@gmail.com

2. **Include details**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)
   - Your contact information for follow-up

3. **Allow time for response**:
   - We will acknowledge receipt within 48 hours
   - We aim to provide an initial assessment within 5 business days
   - We will work with you to coordinate disclosure timeline

## Response Process

1. **Acknowledgment**: We confirm receipt of your report
2. **Investigation**: We assess the vulnerability and determine impact
3. **Fix Development**: We develop and test a fix
4. **Disclosure**: We coordinate public disclosure with you
5. **Release**: We release the fix and publish a security advisory

## Security Best Practices

When using Calculus Animator:

### AI Tutor

- **API Keys**: Store API keys in environment variables, never commit to version control
- **Student Data**: The AI tutor may process student work; ensure compliance with educational privacy laws (FERPA, GDPR)
- **Screenshot Privacy**: Screenshots sent to AI providers should not contain personally identifiable information

### Local Development

- **Virtual Environment**: Always use a virtual environment to isolate dependencies
- **Dependency Scanning**: Run `pip-audit` periodically to check for vulnerable dependencies

### Distribution

- **Packaged Builds**: Download releases only from official GitHub releases
- **Checksum Verification**: Verify SHA256 checksums when available

## Security Posture

The application is designed as a single-user local desktop app. Its security model assumes the host machine is trusted; defenses focus on preventing accidental exposure or misuse rather than multi-tenant threat models.

### Network Boundary

- **FastAPI backend binds to `127.0.0.1` only.** It is unreachable from any non-loopback interface.
- **CORS allow-list is loopback-only**; no `*` wildcard.
- **Request-size limits** are enforced via middleware (`CALCANIM_MAX_REQUEST_BYTES`, default 10 MiB) to prevent memory-exhaustion DoS.

### Error Surface

- All HTTP error responses use a structured envelope (`{"error": {"type", "message", "request_id"}}`).
- Global exception handlers ensure no traceback, file path, or stack-trace text leaks into HTTP response bodies.
- Per-request UUID correlation IDs in JSON-formatted access logs let you replay incidents without exposing internal state to clients.

### Outbound LLM Calls

- **SSRF allowlist** is enforced on every outbound call to LLM providers (DeepSeek, Google, OpenAI, Anthropic, Ollama). URLs are validated against expected per-provider host patterns before the request fires.
- File-URL and metadata-service URL shapes (e.g., `169.254.169.254`) are rejected.
- Cross-provider URL substitution (e.g., a URL claiming to be OpenAI but pointing at a foreign host) is rejected.

### Subprocess Workers

- Render and capacity workers run as isolated subprocesses with bounded `stdin`/`stdout`/`stderr` pipes.
- `stderr` is drained continuously into the project logger so a chatty worker cannot deadlock the parent.
- Render calls have a configurable timeout (`CALC_ANIM_RENDER_TIMEOUT_SEC`, default 60s); on timeout the worker is terminated and a structured error returns.
- A watchdog thread proactively detects worker crashes and restarts them, with bounded restart-storm protection.
- Path-traversal containment guards the temp-file lifecycle in CLI-mode provider integrations (Gemini CLI helpers).

### AI Provider Integration

When using external AI providers:
- Data is sent to third-party services (DeepSeek, Google, OpenAI, etc.)
- Review their privacy policies for educational data handling
- Consider local-only options (Ollama) for sensitive environments
- API keys are read from environment variables; never hardcoded. See `.env.example` for the full list.

### Continuous Verification

- **`pip-audit`** runs on every PR, blocking merges on known vulnerable dependencies.
- **`bandit`** static security analysis runs on every PR over `api/`, `core/`, `ai_tutor/`.
- **CycloneDX SBOM** is generated and attached to every release.
- **`extended-quality.yml`** workflow runs fuzz tests, performance smoke, and E2E UI smoke on a Mon/Thu cron.

### Known-Baseline Items

The following pre-existing items in the auxiliary `tools/` and `slide_renderer/` packages are tracked but not on the OSS POC critical path:
- ANN/BLE/PTH advisory-tier ruff findings on auxiliary scripts
- Mypy type-error backlog in `tools/slide_quality_pipeline.py` and `tools/ollama_slide_reviewer.py`

These will be addressed in a future broad cleanup pass.

## Security Updates

Security updates will be:
- Released as patch versions (e.g., 1.0.1)
- Documented in the [CHANGELOG.md](CHANGELOG.md)
- Announced via GitHub Security Advisories

## Acknowledgments

We thank the following individuals for responsible disclosure:

- *No security researchers acknowledged yet*

## Contact

For security concerns: rubmatsan2001@gmail.com
For general questions: Open a [Discussion](https://github.com/Rsan0948/calculus_animator/discussions)
