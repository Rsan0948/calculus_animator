#!/usr/bin/env python3
"""Build a distributable desktop app with PyInstaller.

Usage:
    python build_release.py
"""
import os
import platform
from pathlib import Path

from PyInstaller.__main__ import run as pyinstaller_run


def main():
    root = Path(__file__).resolve().parent.parent
    sep = ";" if os.name == "nt" else ":"
    app_name = "Calculus Animator"

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
        "--add-data",
        f"{root / 'data' / 'calculus_library.json'}{sep}data",
        "--collect-submodules",
        "webview",
        "--collect-submodules",
        "sympy",
        str(root / "window.py"),
    ]

    system = platform.system().lower()
    if system == "darwin":
        args.extend(["--osx-bundle-identifier", "com.calculusanimator.app"])

    for _a in args:
        pass
    pyinstaller_run(args)


if __name__ == "__main__":
    main()
