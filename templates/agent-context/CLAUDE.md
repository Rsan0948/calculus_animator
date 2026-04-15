# Claude Code Context — [PROJECT NAME]

> This file is loaded automatically by Claude Code at the start of every session.
> It provides project-specific rules that override Claude's default behavior.

---

## Project

**[PROJECT NAME]** — [one-line description]

See `AGENTS.md` for full architecture and guardrail rules.

---

## Mandatory Rules (Claude-Specific)

All rules in `AGENTS.md` apply. These are Claude Code–specific additions:

### Planning

- Before implementing anything non-trivial, run `/plan` and confirm the approach
- For tasks touching >3 files, create a plan file at `.claude/plans/`
- Prefer editing existing files over creating new ones
- Do not create files unless they are strictly necessary

### Implementation

- Make the minimum change required — do not refactor surrounding code
- Do not add docstrings, comments, or type annotations to code you didn't change
- Do not add error handling for scenarios that cannot happen
- Do not add feature flags or backwards-compatibility shims unless asked
- When fixing a bug, fix the root cause — not the symptom

### Before Finishing

Always run before completing any task:

```bash
python ai_helper.py check-all
```

Fix all violations. Do not declare the task done if there are outstanding violations.

### Commits

- Do not commit unless explicitly asked
- Never use `--no-verify`
- Commit messages should explain *why*, not just *what*

---

## MCP Servers

> List any MCP servers configured for this project

```
# Example:
# - filesystem: read/write project files
# - github: create PRs, read issues
# - postgres: query the development database
```

---

## Key Files

| File | Purpose |
|------|---------|
| `AGENTS.md` | Full architecture and guardrail rules |
| `APP.md` | Detailed architecture reference |
| `ai_helper.py` | Run: `python ai_helper.py check-all` before every commit |
| `.env.example` | Required environment variables |

---

## Slash Commands Available

- `/plan` — enter planning mode before implementing
- `/compact` — compress conversation history when context is full
- `/clear` — start fresh session (read AGENTS.md and APP.md first)

---

## Memory Bank

> Persistent context that survives session resets.
> Claude: read this section at the start of every session.

**Current sprint goal:** [What are we building right now?]

**Last session summary:** [What was accomplished in the last session?]

**Blocked on:** [Any blockers or questions that need resolving?]

**Do not touch:** [Files or areas to avoid unless specifically asked]
