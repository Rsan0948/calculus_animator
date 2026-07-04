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
