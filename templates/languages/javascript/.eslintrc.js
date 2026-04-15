/**
 * Engineering Guardrails — JavaScript / TypeScript ESLint Config
 *
 * Enforces the JS/TS equivalents of the Python guardrail rules.
 * Copy this file to your project root as .eslintrc.js
 *
 * Install dependencies:
 *   npm install --save-dev eslint \
 *     @typescript-eslint/parser \
 *     @typescript-eslint/eslint-plugin \
 *     eslint-plugin-security \
 *     eslint-plugin-no-secrets
 *
 * Run:
 *   npx eslint src/ --ext .js,.ts,.tsx
 */

module.exports = {
  root: true,
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: "module",
  },
  plugins: [
    "@typescript-eslint",
    "security",
    "no-secrets",
  ],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:security/recommended",
  ],
  rules: {
    // ── ASI05: No dynamic eval/exec ────────────────────────────────────────────
    // Equivalent: check_unsafe_execution.py
    "no-eval": "error",
    "no-implied-eval": "error",
    "security/detect-eval-with-expression": "error",

    // ── Print statements / logging ─────────────────────────────────────────────
    // Equivalent: check_print_statements.py
    // Disable in test files via ESLint overrides below
    "no-console": ["warn", { allow: ["warn", "error"] }],

    // ── Global state ───────────────────────────────────────────────────────────
    // Equivalent: check_global_state.py
    "no-var": "error",          // Vars are function-scoped (can be global accidentally)
    "prefer-const": "error",    // Prevents reassignment of module-level bindings

    // ── Type safety ────────────────────────────────────────────────────────────
    // Equivalent: check_type_hints.py
    "@typescript-eslint/no-explicit-any": "warn",
    "@typescript-eslint/explicit-function-return-type": "warn",
    "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],

    // ── Secrets ────────────────────────────────────────────────────────────────
    // Equivalent: check_secrets.py + check_agent_credentials.py
    "no-secrets/no-secrets": ["error", { tolerance: 4.0 }],
    "security/detect-possible-timing-attacks": "error",

    // ── Insecure patterns ──────────────────────────────────────────────────────
    // Equivalent: check_pickle_usage.py (serialization risk)
    "security/detect-non-literal-regexp": "warn",
    "security/detect-non-literal-require": "warn",  // Dynamic require = ASI05 equivalent
    "security/detect-object-injection": "warn",

    // ── Code quality ───────────────────────────────────────────────────────────
    "complexity": ["warn", { max: 20 }],     // Equivalent: check_complexity.py
    "max-lines": ["warn", { max: 500 }],     // Equivalent: check_file_size.py
    "eqeqeq": "error",                       // No == (use ===)
    "no-unused-expressions": "error",        // Equivalent: check_dead_code.py partial

    // ── Agent credentials ──────────────────────────────────────────────────────
    // Equivalent: check_agent_credentials.py (ASI03)
    // The no-secrets plugin catches these via entropy analysis, but adding
    // explicit patterns for common AI API key prefixes:
    "no-restricted-syntax": [
      "error",
      {
        // Blocks: const ANTHROPIC_API_KEY = "sk-ant-..."
        selector: "VariableDeclarator[id.name=/^(ANTHROPIC|OPENAI|GOOGLE|COHERE|MISTRAL)_API_KEY$/][init.type='Literal']",
        message: "AI API keys must come from environment variables (process.env.KEY_NAME), not string literals. [ASI03]",
      },
      {
        // Blocks: eval(userInput) — dynamic eval
        selector: "CallExpression[callee.name='eval'][arguments.0.type!='Literal']",
        message: "eval() with dynamic arguments is banned. Use JSON.parse() or redesign. [ASI05]",
      },
    ],
  },

  overrides: [
    // Test files: allow console and relax some rules
    {
      files: ["**/*.test.ts", "**/*.test.js", "**/*.spec.ts", "**/*.spec.js", "tests/**/*"],
      rules: {
        "no-console": "off",
        "@typescript-eslint/no-explicit-any": "off",
      },
    },
    // CLI entry points: allow console
    {
      files: ["**/cli.ts", "**/cli.js", "**/bin/**"],
      rules: {
        "no-console": "off",
      },
    },
  ],
};
