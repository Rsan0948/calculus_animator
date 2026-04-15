# GitHub Copilot Instructions — Engineering Guardrails

This project uses [engineering-guardrails](https://github.com/engineering-guardrails/engineering-guardrails).
23 automated checks run on every commit. Violations block the commit.

## Non-Negotiable Rules

**Code Quality:**
- No absolute paths (`/Users/name/`) — use `Path(__file__).parent` or `os.getenv()`
- No silent exceptions — `except: pass` is banned — use `logger.exception()` or re-raise
- No files over 500 lines — split into modules
- No `subprocess.run(["pip", "install"])` — dependencies go in `pyproject.toml`
- No `pickle`/`joblib` — use JSON, Parquet, or `skops`
- No hardcoded secrets — use `os.getenv("KEY")` + `.env` files
- No `TODO` without ticket: `# TODO(PROJ-123): description`
- No `print()` — use `logging.getLogger(__name__)`
- Type hints required on all new functions
- Max cyclomatic complexity: 20 branches per function
- Min test coverage: 80%

**OWASP Agentic Security:**
- No hardcoded `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc. — use `os.getenv()`
- No `eval(variable)` or `exec(variable)` — only literals allowed
- No `permissions: "all"` in agent role definitions
- Validate all user/agent inputs before using in f-strings or HTTP calls

**Workflow:**
- Minimum change only — do not refactor code you didn't touch
- Write tests before implementation (TDD)
- Run `python ai_helper.py check-all` before finishing

## Architecture

See `AGENTS.md` for full architecture and `APP.md` for module details.
