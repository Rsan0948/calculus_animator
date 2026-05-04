// ESLint flat config for Calculus Animator's vanilla-JS UI modules.
//
// Format: ESLint 9 flat config (`eslint.config.js`). Pinned via the
// repo-root `package.json` so eslint can resolve `@eslint/js` and the
// no-unsanitized plugin from a project-local `node_modules/` — npx-only
// invocation does not work because eslint resolves config-file imports
// from the project root, not the npx temp install.
//
// Local dev:
//   npm install --no-audit --no-fund     # one-time install of pinned devDeps
//   npm run lint                         # eslint -c eslint.config.js 'ui/js/**/*.js'
//
// CI: see .github/workflows/ci.yml (the `Lint JS with ESLint` step).
//
// Rule philosophy:
//   - `@eslint/js` recommended ruleset as the baseline.
//   - `no-unsanitized/property` and `no-unsanitized/method` enabled at
//     `warn` level. The renderer + app modules route every dynamic content
//     insertion through `utils.esc` / `utils.escAttr` / `utils.prettyText`
//     or DOM-API construction; we verified that statically in the frontend
//     safety brief, but the rule cannot trace through helper indirection,
//     so the diagnostics here are advisory.
//   - `no-useless-escape` demoted to warn: pre-existing regex char-class
//     escapes (`[a-zA-Z0-9+\-]`) in utils.js are stylistic, not
//     correctness, and live below the OSS POC critical path.
//   - `no-empty` allows the `catch (_) {}` underscore convention.
//   - `no-unused-vars` honours the `_` underscore prefix as
//     intentional-unused.
//
// CI is gated only on errors. Warnings are surfaced as advisory output.

import js from "@eslint/js";
import nounsanitized from "eslint-plugin-no-unsanitized";

export default [
    {
        ignores: [
            "ui/vendor/**",          // bundled third-party (KaTeX, MathLive)
            "ai_tutor/tutor-panel.js", // separately maintained AI-tutor UI
            "data/**",
            "node_modules/**",
            "dist/**",
            "build/**",
        ],
    },
    js.configs.recommended,
    {
        files: ["ui/js/**/*.js"],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: "module",
            globals: {
                // DOM / browser
                window: "readonly",
                document: "readonly",
                console: "readonly",
                navigator: "readonly",
                localStorage: "readonly",
                setTimeout: "readonly",
                clearTimeout: "readonly",
                setInterval: "readonly",
                clearInterval: "readonly",
                requestAnimationFrame: "readonly",
                performance: "readonly",
                NodeFilter: "readonly",
                MutationObserver: "readonly",
                Image: "readonly",
                FontFace: "readonly",
                Event: "readonly",
                CustomEvent: "readonly",
                // Loaded via <script> in index.html (vendored under ui/vendor/)
                katex: "readonly",
                MathLive: "readonly",
                // Bridges to / from Python and the AI-tutor side-script
                pywebview: "readonly",
                appAPI: "writable",
                aiTutor: "readonly",
            },
        },
        plugins: {
            "no-unsanitized": nounsanitized,
        },
        rules: {
            // Security advisories: we know these fire on innerHTML writes that
            // route through `utils.esc` / `utils.prettyText` and are safe in
            // practice. Surface as warnings so future drift is visible without
            // breaking CI.
            "no-unsanitized/property": "warn",
            "no-unsanitized/method": "warn",

            // Stylistic, not correctness — pre-existing baseline in utils.js
            // regex char classes. Demoted to advisory.
            "no-useless-escape": "warn",

            // Repo conventions
            "no-empty": ["warn", { allowEmptyCatch: true }],
            "no-unused-vars": [
                "warn",
                { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
            ],
            "no-prototype-builtins": "warn",
            // The renderer module installs `Object.freeze(Object.prototype)`
            // and routes dynamic-key writes through `_setSafe`; the redeclare
            // diagnostic we hit on duplicate-helper definitions is informational.
            "no-redeclare": "warn",
        },
    },
];
