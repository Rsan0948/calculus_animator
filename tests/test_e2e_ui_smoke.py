from __future__ import annotations

import contextlib
import http.server
import os
import socketserver
import threading
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")


@contextlib.contextmanager
def _serve_dir(directory: Path):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

        def log_message(self, fmt, *args):  # pragma: no cover - silence test output
            return

    with socketserver.TCPServer(("127.0.0.1", 0), Handler) as httpd:
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{port}"
        finally:
            httpd.shutdown()
            thread.join(timeout=2)


def _launch_browser(p):
    """Launch Chromium, honouring CALC_ANIM_CHROMIUM as an executable override.

    Sandboxed/remote environments often pre-install a Chromium whose build
    number doesn't match the pinned playwright's expected download; the env
    var lets those environments run the e2e suite without re-downloading.
    """
    exe = os.environ.get("CALC_ANIM_CHROMIUM") or None
    return p.chromium.launch(headless=True, executable_path=exe)


@contextlib.contextmanager
def _ui_page():
    root = Path(__file__).resolve().parent.parent
    with _serve_dir(root / "ui") as base_url:
        with playwright.sync_playwright() as p:
            browser = _launch_browser(p)
            page = browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
            page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
            try:
                yield page, errors
            finally:
                browser.close()


@pytest.mark.e2e
def test_ui_static_shell_loads_and_core_nav_visible():
    with _ui_page() as (page, errors):
        # Static shell should be visible regardless of pywebview availability.
        assert page.locator("button[data-screen='solver']").is_visible()
        assert page.locator("button[data-screen='learning']").is_visible()
        assert page.locator("#solveBtn").is_visible()
        assert page.locator("#demoSelect").is_visible()

        # Learning screen can be activated by clicking tab.
        page.click("button[data-screen='learning']")
        assert page.locator("#learningScreen").is_visible()
        assert not errors, errors


@pytest.mark.e2e
def test_tutor_panel_accessibility_and_backdrop_dismiss():
    with _ui_page() as (page, errors):
        page.wait_for_selector("#ai-tutor-panel", state="attached")

        # Dialog semantics and labelled critical controls.
        assert page.locator("#ai-tutor-panel[role='dialog'][aria-modal='true']").count() == 1
        assert page.locator("#tutor-close[aria-label]").count() == 1
        assert page.locator("#tutor-toggle[aria-label]").count() == 1

        # Open via toggle; tapping the backdrop dismisses (modal escape).
        page.locator("#tutor-toggle").click()
        assert "open" in (page.locator("#ai-tutor-panel").get_attribute("class") or "")
        page.locator("#ai-tutor-backdrop").click(position={"x": 10, "y": 10})
        page.wait_for_timeout(200)
        assert "open" not in (page.locator("#ai-tutor-panel").get_attribute("class") or "")
        assert not errors, errors


# Minimal fake pywebview bridge: enough for boot() and one solve round
# trip, so e2e tests can exercise the full solver UI without Python.
_FAKE_PYWEBVIEW = """
window.pywebview = { api: {
    log_to_python: async () => {},
    get_formulas: async () => JSON.stringify({categories: [], formulas: []}),
    get_demo_problems: async () => JSON.stringify({collections: []}),
    get_symbols: async () => JSON.stringify({groups: []}),
    get_learning_library: async () =>
        JSON.stringify({categories: [], symbols: [], formulas: [], topics: []}),
    get_curriculum: async () => JSON.stringify({pathways: []}),
    get_glossary: async () => JSON.stringify({terms: []}),
    solve: async () => JSON.stringify({
        success: true, result: "2*x", result_latex: "2 x",
        steps: [], animation_steps: [], detected_type: "DERIVATIVE"
    }),
    get_graph_data: async () => JSON.stringify({success: false, error: "stub"}),
}};
"""


@pytest.mark.e2e
def test_enter_key_solves_and_records_recent_expression():
    root = Path(__file__).resolve().parent.parent
    with _serve_dir(root / "ui") as base_url:
        with playwright.sync_playwright() as p:
            browser = _launch_browser(p)
            page = browser.new_page()
            page.add_init_script(_FAKE_PYWEBVIEW)
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
            page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
            page.wait_for_timeout(600)  # let boot() finish

            # No recents on a fresh profile.
            assert not page.locator("#recentExpressions").is_visible()

            # Type an expression and press Enter — must solve, not newline.
            page.locator("#mathInput").fill("x^3")
            page.locator("#mathInput").press("Enter")
            page.wait_for_timeout(400)
            assert "\n" not in page.locator("#mathInput").input_value()
            assert "2 x" in (page.locator("#resultDisplay").inner_text() or "")

            # The tutor context must sync on the Enter path too (the
            # integration wraps appAPI.solve, not just the button click).
            tutor_expr = page.evaluate(
                "window.aiTutor && window.aiTutor.solverState"
                " && window.aiTutor.solverState.expression"
            )
            assert tutor_expr and "x" in tutor_expr

            # The solve is recorded as a recent chip and persisted.
            chips = page.locator("#recentExpressions .recent-chip")
            assert chips.count() == 1
            stored = page.evaluate("localStorage.getItem('calcAnimRecents')")
            assert "x" in stored

            # Solving another expression prepends; clicking a chip reloads it.
            page.locator("#mathInput").fill("sin(x)")
            page.locator("#mathInput").press("Enter")
            page.wait_for_timeout(400)
            chips = page.locator("#recentExpressions .recent-chip")
            assert chips.count() == 2
            chips.nth(1).click()  # older entry: x^3 (displayed as x³)
            value = page.locator("#mathInput").input_value()
            assert value and "sin" not in value

            # Shift+Enter still inserts a newline (multi-line editing).
            # Note: the input normalizer trims edge whitespace, so test a
            # mid-text newline — the realistic multi-line editing spot.
            page.locator("#mathInput").fill("x+y")
            page.evaluate("document.getElementById('mathInput').setSelectionRange(1, 1)")
            page.locator("#mathInput").press("Shift+Enter")
            assert "\n" in page.locator("#mathInput").input_value()

            assert not errors, errors
            browser.close()


@pytest.mark.e2e
def test_tutor_panel_hidden_on_learning_screen():
    with _ui_page() as (page, errors):
        page.wait_for_selector("#ai-tutor-panel", state="attached")

        page.click("button[data-screen='learning']")
        assert page.locator("#learningScreen").is_visible()

        # Programmatic open (the reachable path: openLearningTopic switches
        # screens while the panel is open) must stay CSS-hidden along with
        # the click-swallowing backdrop.
        page.evaluate("window.aiTutor.open()")
        page.wait_for_timeout(200)
        assert not page.locator("#ai-tutor-panel").is_visible()
        assert not page.locator("#ai-tutor-backdrop").is_visible()

        # The ?// shortcut is gated on the Learning screen.
        page.evaluate("window.aiTutor.close()")
        page.keyboard.press("/")
        page.wait_for_timeout(200)
        assert "open" not in (page.locator("#ai-tutor-panel").get_attribute("class") or "")

        # Back on the solver screen the opened panel re-appears.
        page.evaluate("window.aiTutor.open()")
        page.click("button[data-screen='solver']")
        page.wait_for_timeout(200)
        assert page.locator("#ai-tutor-panel").is_visible()
        assert not errors, errors
