#!/usr/bin/env python3
"""Packaged app entry point (no runtime pip installs)."""
import os

import webview

from api.bridge import CalculusAPI


def launch(api: CalculusAPI) -> None:
    """Create and start the pywebview window. Single source of truth for window config."""
    ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "index.html")
    webview.create_window(
        title="Calculus Animator",
        url=ui_path,
        js_api=api,
        width=1440,
        height=920,
        resizable=True,
        min_size=(1024, 700),
    )
    webview.start(debug=False)


def main():
    launch(CalculusAPI())


if __name__ == "__main__":
    main()
