#!/usr/bin/env python3
"""Run lint, typing, tests, and optional security checks in one command."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _venv_python() -> Path:
    if sys.platform.startswith("win"):
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def _run(cmd: list[str]) -> int:
    print("$", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT))


def main() -> int:
    include_security = "--security" in sys.argv
    py = _venv_python()
    interpreter = str(py if py.exists() else Path(sys.executable))

    steps = [
        [interpreter, "-m", "ruff", "check", "."],
        [interpreter, "-m", "mypy", "api", "core"],
        [interpreter, "run_tests.py"],
    ]
    if include_security:
        steps.append([interpreter, "-m", "pip_audit"])

    for cmd in steps:
        code = _run(cmd)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

