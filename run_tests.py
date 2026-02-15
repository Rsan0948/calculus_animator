#!/usr/bin/env python3
"""One-click test runner for local development.

Usage:
  python run_tests.py
  python run_tests.py --quick
  python run_tests.py --full
  python run_tests.py --fuzz
  python run_tests.py --perf
  python run_tests.py --e2e
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _venv_python() -> Path:
    if sys.platform.startswith("win"):
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def main() -> int:
    quick = "--quick" in sys.argv
    full = "--full" in sys.argv
    fuzz = "--fuzz" in sys.argv
    perf = "--perf" in sys.argv
    e2e = "--e2e" in sys.argv
    py = _venv_python()
    interpreter = str(py if py.exists() else Path(sys.executable))

    marker_expr = "not e2e and not perf and not fuzz"
    if full:
        marker_expr = ""
    elif e2e:
        marker_expr = "e2e"
    elif perf:
        marker_expr = "perf"
    elif fuzz:
        marker_expr = "fuzz"

    if quick:
        cmd = [interpreter, "-m", "pytest", "-q"]
        if marker_expr:
            cmd.extend(["-m", marker_expr])
    else:
        cmd = [
            interpreter,
            "-m",
            "pytest",
            "--cov=api",
            "--cov=core",
            "--cov-report=term-missing",
            "-q",
        ]
        if marker_expr:
            cmd.extend(["-m", marker_expr])

    print("$", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
