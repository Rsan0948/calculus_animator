# Starting a New Task — [PROJECT NAME]

Copy and paste this as your first message when starting a new coding session with an AI agent.

---

## Template (fill in the [brackets])

```
I need you to [describe the task clearly — be specific about what should change and why].

## Project Context

This project uses engineering-guardrails. Your code MUST pass all 23 guardrail checks
before I will accept it. Run `python ai_helper.py check-all` before finishing.

## Non-Negotiable Rules

1. NO absolute paths — use Path(__file__).parent or os.getenv()
2. NO silent exceptions — except: pass is banned
3. NO hardcoded secrets — use os.getenv() + .env files
4. NO eval/exec with dynamic arguments
5. NO hardcoded AI API keys (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)
6. Type hints on all new functions
7. Tests required for new logic (80% coverage minimum)
8. Max 500 lines per file — split if needed
9. Use logging, not print()
10. No TODO comments without a ticket reference

## Architecture Reference

See APP.md for the full architecture map before touching any files.
See AGENTS.md for the complete guardrail rules.

## Definition of Done

- [ ] All 23 guardrail checks pass (`python ai_helper.py check-all`)
- [ ] Tests written and passing
- [ ] No new violations introduced
- [ ] Code does only what was asked — no extra features or refactoring
```

---

## Tips for Effective Prompting

**Be specific about scope:**
> "Add a `/users/{id}/deactivate` endpoint. It should set `users.active = False` in the DB. Do not touch any other routes or models."

**Reference existing patterns:**
> "Follow the same pattern as `src/api/routes/orders.py` for the new endpoint."

**Set explicit constraints:**
> "Do not add new dependencies. Use only what's already in `pyproject.toml`."

**Ask for a plan first on complex tasks:**
> "Before writing any code, explain your approach and which files you'll touch."
