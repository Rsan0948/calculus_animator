from __future__ import annotations

import contextlib
import http.server
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


@pytest.mark.e2e
def test_ui_static_shell_loads_and_core_nav_visible():
    root = Path(__file__).resolve().parent.parent
    ui_root = root / "ui"
    with _serve_dir(ui_root) as base_url:
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")

            # Static shell should be visible regardless of pywebview availability.
            assert page.locator("button[data-screen='solver']").is_visible()
            assert page.locator("button[data-screen='learning']").is_visible()
            assert page.locator("#solveBtn").is_visible()
            assert page.locator("#demoSelect").is_visible()

            # Learning screen can be activated by clicking tab.
            page.click("button[data-screen='learning']")
            assert page.locator("#learningScreen").is_visible()
            browser.close()

