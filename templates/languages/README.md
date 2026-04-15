# Multi-Language Support

engineering-guardrails is Python-first. Python guardrails run via AST analysis and are the reference implementation.

Other languages are supported through configuration files + GitHub Actions workflows. The philosophy is the same — enforce the same anti-patterns, just with language-native tooling.

---

## Current Language Support

| Language | Tooling | Status |
|----------|---------|--------|
| Python | AST + custom scripts | ✅ Full (reference) |
| JavaScript / TypeScript | ESLint + security plugins | ✅ Template |
| Go | golangci-lint | Planned |
| Rust | clippy | Planned |

---

## JavaScript / TypeScript

Copy the config files to your JS/TS project root:

```bash
cp templates/languages/javascript/.eslintrc.js .
cp templates/languages/javascript/.github/workflows/js-guardrails.yml .github/workflows/
```

Install dependencies:

```bash
npm install --save-dev eslint @typescript-eslint/parser @typescript-eslint/eslint-plugin eslint-plugin-security eslint-plugin-no-secrets
```

The config enforces:

| ESLint Rule | Equivalent Python Guardrail |
|------------|----------------------------|
| `no-eval` | `check_unsafe_execution.py` (ASI05) |
| `no-console` | `check_print_statements.py` |
| `prefer-const` / `no-var` | `check_global_state.py` |
| `@typescript-eslint/no-explicit-any` | `check_type_hints.py` |
| `security/detect-*` | `check_secrets.py`, `check_supply_chain.py` |
| `no-secrets/no-secrets` | `check_secrets.py` |

---

## Adding a New Language

1. Create `templates/languages/<language>/` directory
2. Add a linter config file that enforces the equivalent rules (see table above as a guide)
3. Add `.github/workflows/<language>-guardrails.yml` that runs the linter on every PR
4. Update this README with the new language entry
5. Open a PR — include example violations and the ESLint/linter output

The minimum set of rules to enforce for any language:
- No hardcoded secrets
- No `eval`-equivalent with dynamic input
- No overly complex functions
- Type safety / type hints where the language supports them
- No debug/print statements in production code

---

## Philosophy

The guardrails are language-agnostic concepts. The implementations are language-specific. If you're adding a language, think about these questions:

- How does this language serialize data? (Equivalent of pickle risk)
- How does this language handle exceptions? (Equivalent of silent-exceptions risk)
- What does "dead code" look like? (Equivalent of dead-code risk)
- How are secrets typically leaked? (Usually env vars or config files)

Answering these shapes the right rule set.
