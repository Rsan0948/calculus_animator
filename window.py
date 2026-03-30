#!/usr/bin/env python3
import sys
import webview

from api.bridge import CalculusAPI
from config import UI_DIR

# Track if window is already created (prevents double-launch on macOS)
_window_created = False


def launch(api: CalculusAPI) -> None:
    """Create and start the pywebview window. Single source of truth for window config."""
    global _window_created
    
    # Prevent double window creation on macOS multiprocessing spawn
    if _window_created:
        return
    _window_created = True
    
    ui_path = str(UI_DIR / "index.html")
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
    # Required for multiprocessing on macOS/Windows
    if sys.platform in ('darwin', 'win32'):
        import multiprocessing
        multiprocessing.freeze_support()
    main()
