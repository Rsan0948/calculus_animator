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
    root = Path(__file__).resolve().parent
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
        f"{root / 'calculus_library.json'}{sep}.",
        "--collect-submodules",
        "webview",
        "--collect-submodules",
        "sympy",
        str(root / "app_main.py"),
    ]

    system = platform.system().lower()
    if system == "darwin":
        args.extend(["--osx-bundle-identifier", "com.calculusanimator.app"])

    print("Running PyInstaller with args:")
    for a in args:
        print(" ", a)
    pyinstaller_run(args)
    print("\nBuild complete.")
    print("Artifacts:")
    print(f"  {root / 'dist'}")
    print(f"  {root / 'build'}")


if __name__ == "__main__":
    main()
