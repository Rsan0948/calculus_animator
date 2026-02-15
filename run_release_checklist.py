#!/usr/bin/env python3
"""Release readiness runner + checklist report generator.

Usage:
  python run_release_checklist.py
  python run_release_checklist.py --skip-e2e
  python run_release_checklist.py --skip-perf
  python run_release_checklist.py --quick
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)


@dataclass
class StepResult:
    label: str
    command: list[str]
    returncode: int
    duration_s: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _venv_python() -> Path:
    if sys.platform.startswith("win"):
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def _run(label: str, cmd: list[str]) -> StepResult:
    print(f"\n== {label} ==")
    print("$", " ".join(cmd))
    t0 = time.perf_counter()
    code = subprocess.call(cmd, cwd=str(ROOT))
    dt = time.perf_counter() - t0
    return StepResult(label=label, command=cmd, returncode=code, duration_s=dt)


def _write_report(results: list[StepResult], quick: bool, skip_perf: bool, skip_e2e: bool) -> Path:
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%SZ")
    latest = REPORTS / "release_checklist_latest.md"
    stamped = REPORTS / f"release_checklist_{ts}.md"

    lines: list[str] = []
    lines.append("# Release Checklist Report")
    lines.append("")
    lines.append(f"- Generated (UTC): `{datetime.now(UTC).isoformat().replace('+00:00', 'Z')}`")
    lines.append(f"- Mode: `quick={quick}`, `skip_perf={skip_perf}`, `skip_e2e={skip_e2e}`")
    lines.append("")
    lines.append("## Automated Gates")
    lines.append("")
    for r in results:
        status = "PASS" if r.ok else "FAIL"
        lines.append(
            f"- [{status}] **{r.label}** (`{r.duration_s:.1f}s`)  \n"
            f"  Command: `{ ' '.join(r.command) }`"
        )
    lines.append("")

    all_ok = all(r.ok for r in results)
    lines.append("## Summary\n")
    lines.append(f"- Overall automated status: **{'PASS' if all_ok else 'FAIL'}**")
    lines.append("")
    lines.append("## Manual Release Checks")
    lines.append("")
    lines.append("- [ ] Launch app and verify home screen loads")
    lines.append("- [ ] Problem Solver: solve 3 representative inputs (derivative, limit, integral)")
    lines.append("- [ ] Problem Solver: verify graph renders + legend labels are readable")
    lines.append("- [ ] Learning: open pathway, navigate next/previous, open/close notes")
    lines.append("- [ ] Learning: verify quiz placeholder progression works")
    lines.append("- [ ] Verify copy buttons (expression/visual/text output) work as expected")
    lines.append("- [ ] Package/open distribution build (`dist/`) on target OS")
    lines.append("")

    content = "\n".join(lines) + "\n"
    latest.write_text(content, encoding="utf-8")
    stamped.write_text(content, encoding="utf-8")
    return latest


def main() -> int:
    args = set(sys.argv[1:])
    skip_e2e = "--skip-e2e" in args
    skip_perf = "--skip-perf" in args
    quick = "--quick" in args

    py = _venv_python()
    interpreter = str(py if py.exists() else Path(sys.executable))

    steps: list[StepResult] = []
    steps.append(_run("Quality Gate (ruff + mypy + tests)", [interpreter, "run_quality.py"]))
    if not steps[-1].ok:
        report_path = _write_report(steps, quick=quick, skip_perf=skip_perf, skip_e2e=skip_e2e)
        print(f"\nRelease checklist failed. Report: {report_path}")
        return 1

    if not skip_perf:
        steps.append(_run("Performance Smoke Tests", [interpreter, "run_tests.py", "--perf"]))
        if not steps[-1].ok:
            report_path = _write_report(steps, quick=quick, skip_perf=skip_perf, skip_e2e=skip_e2e)
            print(f"\nRelease checklist failed. Report: {report_path}")
            return 1

    if not skip_e2e:
        e2e_cmd = [interpreter, "run_tests.py", "--e2e"]
        if quick:
            e2e_cmd = [interpreter, "-m", "pytest", "-q", "-m", "e2e", "tests/test_e2e_backend_smoke.py"]
        steps.append(_run("E2E Smoke Tests", e2e_cmd))
        if not steps[-1].ok:
            report_path = _write_report(steps, quick=quick, skip_perf=skip_perf, skip_e2e=skip_e2e)
            print(f"\nRelease checklist failed. Report: {report_path}")
            return 1

    report_path = _write_report(steps, quick=quick, skip_perf=skip_perf, skip_e2e=skip_e2e)
    print(f"\nRelease checklist passed. Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
