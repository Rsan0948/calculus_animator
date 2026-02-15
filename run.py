#!/usr/bin/env python3
"""Single entry point — auto-installs dependencies, then launches the app."""
import importlib
import os
import subprocess
import sys

REQUIRED = {
    "webview": "pywebview>=4.4",
    "sympy": "sympy>=1.12",
    "numpy": "numpy>=1.24",
    "pygame": "pygame>=2.5",
    "antlr4": "antlr4-python3-runtime==4.11.1",
}

def ensure_deps():
    missing = []
    for mod, pkg in REQUIRED.items():
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"Installing missing packages: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing, "-q"])

ensure_deps()

def main():
    import webview
    from api.bridge import CalculusAPI

    api = CalculusAPI()
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

if __name__ == "__main__":
    main()
