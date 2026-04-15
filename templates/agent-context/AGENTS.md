# Agent Context — [PROJECT NAME]

> This file is the primary context document for AI coding agents (Claude Code, Cursor, Cline, Copilot, etc.).
> Keep it up to date as the project evolves. The agent reads this at the start of every session.

---

## Project Overview

**Name:** [PROJECT NAME]
**Purpose:** [One-sentence description of what this project does]
**Stack:** [e.g., Python 3.11, FastAPI, PostgreSQL, React]
**Repo:** [GitHub URL]

---

## Architecture

[Replace with your actual architecture. Example:]

```
src/
├── api/          # FastAPI routes and middleware
├── core/         # Business logic (no framework dependencies)
├── db/           # Database models and migrations
├── services/     # External service integrations
└── utils/        # Shared utilities

tests/            # Mirrors src/ structure
```

**Data flow:** [e.g., Request → API layer → Service layer → DB → Response]

**Key decisions:**
- [Architectural decision 1 and why]
- [Architectural decision 2 and why]

---

## Engineering Guardrails — MANDATORY RULES

This project enforces [engineering-guardrails](https://github.com/engineering-guardrails/engineering-guardrails).
**Your code WILL be rejected at commit time if you violate these rules.**

### Code Quality (enforced at every commit)

1. **NO ABSOLUTE PATHS** — Use `Path(__file__).parent` or env vars. Never `/Users/name/...`
2. **NO SILENT EXCEPTIONS** — `except: pass` and `except: return None` are blocked. Use `logger.exception()` or re-raise.
3. **MAX 500 LINES PER FILE** — Split large files into modules. Single Responsibility Principle.
4. **NO RUNTIME PIP INSTALLS** — No `subprocess.run(["pip", "install", ...])` in source code.
5. **NO PICKLE/JOBLIB** — Use JSON, Parquet, or `skops` for serialization. Pickle enables arbitrary code execution.
6. **NO HARDCODED SECRETS** — No API keys, passwords, or tokens in source. Use `os.getenv()` + `.env` files.
7. **NO ORPHAN TODOs** — All TODOs must reference a ticket: `# TODO(PROJ-123): description`
8. **NO CIRCULAR IMPORTS** — Design modules to have clear dependency direction.
9. **NO DEAD CODE** — Remove unused imports, functions, and variables before committing.
10. **MAX CYCLOMATIC COMPLEXITY 20** — If a function has >20 branches, split it.
11. **TESTS REQUIRED** — Minimum 80% coverage. Write failing tests before implementation.
12. **README EXAMPLES MUST RUN** — All Python code blocks in README.md must execute without error.
13. **DEPENDENCIES MUST BE CURRENT** — No packages older than 365 days without justification.
14. **NO HARDCODED INTERNAL URLs** — Use `os.getenv("API_URL")` for environment-specific URLs.
15. **NO PRINT STATEMENTS** — Use `logging.getLogger(__name__)` instead of `print()`.
16. **NO LARGE BINARIES IN GIT** — Models, datasets, and large files belong in object storage (S3, GCS, DVC).
17. **TYPE HINTS REQUIRED** — All function parameters and return values must be annotated.
18. **NO MUTABLE GLOBALS** — No module-level `dict`, `list`, or `set` that changes at runtime.

### OWASP Agentic Top 10 (enforced at commit/push)

19. **VALIDATE ALL AGENT INPUTS** — `user_input`, `prompt`, `query` variables must be validated before flowing into f-strings or HTTP calls (ASI01).
20. **NO HARDCODED AI API KEYS** — `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc. must come from environment variables (ASI03).
21. **NO DYNAMIC EVAL/EXEC** — `eval(variable)` and `exec(variable)` are blocked. Only `eval("literal")` is allowed (ASI05).
22. **NO VULNERABLE PACKAGES** — `pip-audit` runs at push time. No packages with CRITICAL or HIGH CVEs (ASI04).
23. **PRINCIPLE OF LEAST PRIVILEGE** — Agent role definitions must not use `permissions: "all"` or `role: "admin"` (ASI03).

---

## Development Workflow

### Before Every Commit

```bash
# Check all guardrails (runs all 23 checks)
python ai_helper.py check-all

# If violations exist, fix them before committing.
# Do not use --no-verify to bypass the checks.
```

### Adding New Code

1. Write a failing test first (`tests/` mirrors `src/`)
2. Write the minimum implementation to make it pass
3. Run `python ai_helper.py check-all`
4. Fix all violations
5. Commit

### Running the Project

```bash
# [Replace with your actual commands]
pip install -e ".[dev]"
python -m pytest tests/
python -m uvicorn src.api.main:app --reload
```

### Environment Variables Required

```bash
# Copy .env.example to .env and fill in values
cp .env.example .env

# Required variables:
# DATABASE_URL=postgresql://user:pass@localhost/dbname
# API_KEY=<from secret manager>
```

---

## Memory Bank

> Update these sections as the project evolves. The agent reads them every session.

### Current Sprint Goal

[What is the team trying to accomplish this sprint?]

### Known Issues / Technical Debt

- [ ] [Issue 1 — brief description and ticket reference]
- [ ] [Issue 2 — brief description and ticket reference]

### Recent Architecture Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| [DATE] | [Decision] | [Why] |

### Files to Be Careful With

- `[path/to/file.py]` — [Why it's sensitive, e.g., "touches payment logic"]
- `[path/to/config.py]` — [Why, e.g., "controls feature flags for all environments"]

---

## What NOT to Do

- Do not add `# type: ignore` without a comment explaining why
- Do not add `continue-on-error: true` to CI without team discussion
- Do not commit `.env` files (they are in `.gitignore`)
- Do not merge to `main` without passing CI
- Do not use `--no-verify` to bypass pre-commit hooks
- Do not hardcode environment-specific values (URLs, ports, credentials)
