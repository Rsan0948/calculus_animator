#!/usr/bin/env python3
"""Build a distributable desktop app with PyInstaller.

Entry point is ``window.py`` — the PyWebView shell. The AI-tutor FastAPI
backend is intentionally NOT bundled into the artifact today: it ships as
an optional ``[ai_tutor]`` install group via ``pyproject.toml``. A future
brief should decide whether the release ships with the tutor backend
embedded or as a sidecar; until then this script produces the core
animator.

Build deps (PyInstaller) live in the ``[build]`` extras group of
``pyproject.toml``. Install them with one of:

    pip install -e .[build]                # editable + build extras
    pip install pyinstaller==6.20.0        # standalone, pinned version

Usage:
    pip install -e .[build]
    python scripts/build_release.py
"""
import os
import platform
from pathlib import Path

from PyInstaller.__main__ import run as pyinstaller_run


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    sep = ";" if os.name == "nt" else ":"
    app_name = "Calculus Animator"

    # Note: ``--add-data {root}/data{sep}data`` already bundles the whole
    # ``data/`` directory (curriculum + library + capacity report). We
    # intentionally do NOT add ``data/calculus_library.json`` a second time
    # — duplicate entries trip a PyInstaller conflict warning at build
    # time and can shadow the directory copy on extraction.
    args = [
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        app_name,
        "--paths",
        str(root),
        "--add-data",
        f"{root / 'ui'}{sep}ui",
        "--add-data",
        f"{root / 'data'}{sep}data",
        "--collect-submodules",
        "webview",
        "--collect-submodules",
        "sympy",
        str(root / "window.py"),
    ]

    system = platform.system().lower()
    if system == "darwin":
        args.extend(["--osx-bundle-identifier", "com.calculusanimator.app"])

    pyinstaller_run(args)


if __name__ == "__main__":
    main()
