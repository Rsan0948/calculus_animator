/**
 * Space bridge — browser-side polyfill for `window.pywebview.api`.
 *
 * On the desktop (PyWebView) the JS bridge `window.pywebview.api` is injected
 * by the host shell and proxies calls into `api/bridge.py:CalculusAPI`. In the
 * Docker Space deployment there is no PyWebView, so this module installs a
 * compatible shim that translates each public CalculusAPI method into an
 * HTTP fetch against the FastAPI `/api/*` endpoints Lane A wires up.
 *
 * Contract mirrors the desktop shape:
 *   - Each method returns `Promise<string>` — the body of the backend
 *     response, unparsed. Callers (e.g. `ui/js/modules/bridge.js`) already
 *     `JSON.parse(...)` the result.
 *   - GET endpoints take no params; POST endpoints carry a JSON body whose
 *     keys match the Python kwarg names so the FastAPI handler can
 *     `**body` straight through to the bridge method.
 *   - Network / non-2xx errors propagate as Promise rejections, matching
 *     how `pywebview.api.X(...)` would throw on bridge failure. The desktop
 *     `bridge.js` wrappers already catch these.
 *
 * Side-effect-only module: nothing is exported. Import for the install:
 *   import './modules/space_bridge.js';
 *
 * The shim is conditional: if `window.pywebview` is already present (i.e.
 * we are running inside PyWebView and the host has injected the real bridge
 * before this module evaluates), installation is skipped and the module is
 * a no-op.
 */

const HEADERS_JSON = { "Content-Type": "application/json" };

async function postJson(path, payload) {
    const res = await fetch(path, {
        method: "POST",
        headers: HEADERS_JSON,
        body: JSON.stringify(payload),
    });
    return res.text();
}

async function getText(path) {
    const res = await fetch(path);
    return res.text();
}

function buildShimApi() {
    return {
        // Logging — fire-and-forget. We swallow rejections so a flaky
        // /api/log_to_python doesn't surface as an unhandled-promise warning
        // on every call from `bridge.log`.
        log_to_python(msg, level) {
            return postJson("/api/log_to_python", { msg, level }).catch(() => "");
        },

        // Reference data getters — Python returns a JSON string; we forward
        // the response body verbatim.
        get_formulas() {
            return getText("/api/get_formulas");
        },
        get_symbols() {
            return getText("/api/get_symbols");
        },
        get_demo_problems() {
            return getText("/api/get_demo_problems");
        },
        get_learning_library() {
            return getText("/api/get_learning_library");
        },
        get_curriculum() {
            return getText("/api/get_curriculum");
        },
        get_glossary() {
            return getText("/api/get_glossary");
        },

        // Solver pipeline. `params` arrives here pre-stringified (the desktop
        // JS bridge calls `pywebview.api.solve(latex, calcType, JSON.stringify(params))`),
        // so we forward it as a string field for the FastAPI handler to
        // pass straight through to the Python bridge.
        solve(latex_str, calc_type, params) {
            return postJson("/api/solve", { latex_str, calc_type, params });
        },
        get_graph_data(latex_str, calc_type, params, x_min, x_max) {
            return postJson("/api/get_graph_data", {
                latex_str,
                calc_type,
                params,
                x_min,
                x_max,
            });
        },

        // Slide rendering — both the curriculum slide and the capacity test.
        render_learning_slide(pathway_id, chapter_id, slide_index, width, height) {
            return postJson("/api/render_learning_slide", {
                pathway_id,
                chapter_id,
                slide_index,
                width,
                height,
            });
        },
        capacity_test_slide(text, with_image, page_index, width, height) {
            return postJson("/api/capacity_test_slide", {
                text,
                with_image,
                page_index,
                width,
                height,
            });
        },
    };
}

if (typeof window.pywebview === "undefined") {
    window.pywebview = { api: buildShimApi() };
}
