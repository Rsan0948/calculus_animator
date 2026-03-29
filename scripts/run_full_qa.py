#!/usr/bin/env python3
"""One-shot QA pipeline runner.

Default behavior:
1) Install runtime + dev dependencies
2) Install Playwright Chromium
3) Run lint + typing + default tests
4) Run fuzz tests
5) Run perf smoke tests
6) Run e2e smoke tests

Usage:
  python run_full_qa.py
  python run_full_qa.py --skip-install
  python run_full_qa.py --no-e2e
  python run_full_qa.py --no-fuzz
  python run_full_qa.py --security
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _venv_python() -> Path:
    if sys.platform.startswith("win"):
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def _run(cmd: list[str], label: str) -> int:
    return subprocess.call(cmd, cwd=str(ROOT))


def _install_deps_fallback(interpreter: str) -> int:
    req = ROOT / "requirements.txt"
    dev_req = ROOT / "requirements-dev.txt"
    steps = [
        ([interpreter, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], "Upgrade pip tooling"),
    ]
    if req.exists():
        steps.append(([interpreter, "-m", "pip", "install", "-r", str(req)], "Install runtime requirements"))
    if dev_req.exists():
        steps.append(([interpreter, "-m", "pip", "install", "-r", str(dev_req)], "Install dev requirements"))
    else:
        steps.append(([interpreter, "-m", "pip", "install", "pytest", "pytest-cov", "ruff", "mypy"], "Install core dev tools"))

    for cmd, label in steps:
        code = _run(cmd, label)
        if code != 0:
            return code
    return 0


def main() -> int:
    args = set(sys.argv[1:])
    skip_install = "--skip-install" in args
    run_e2e = "--no-e2e" not in args
    run_fuzz = "--no-fuzz" not in args
    include_security = "--security" in args

    py = _venv_python()
    interpreter = str(py if py.exists() else Path(sys.executable))

    if not skip_install:
        setup_script = ROOT / "setup_test_env.py"
        if setup_script.exists():
            code = _run([interpreter, str(setup_script.name)], "Install Runtime + Dev Dependencies")
        else:
            code = _install_deps_fallback(interpreter)
        if code != 0:
            return code

    if run_e2e:
        code = _run([interpreter, "-m", "playwright", "install", "chromium"], "Install Playwright Chromium")
        if code != 0:
            return code

    # Lint + type + default tests
    quality_cmd = [interpreter, "scripts/run_quality.py"]
    if include_security:
        quality_cmd.append("--security")
    code = _run(quality_cmd, "Run Quality Gate")
    if code != 0:
        return code

    if run_fuzz:
        code = _run([interpreter, "scripts/run_tests.py", "--fuzz"], "Run Fuzz Tests")
        if code != 0:
            return code

    code = _run([interpreter, "scripts/run_tests.py", "--perf"], "Run Performance Smoke Tests")
    if code != 0:
        return code

    if run_e2e:
        code = _run([interpreter, "scripts/run_tests.py", "--e2e"], "Run E2E Smoke Tests")
        if code != 0:
            return code

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
