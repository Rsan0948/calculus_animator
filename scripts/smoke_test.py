#!/usr/bin/env python3
"""Smoke test for Calculus Animator.

Verifies the install-and-launch path end-to-end without launching the
WebView. Three checks, in order:

  1. ``ai_tutor.main.create_app`` constructs a FastAPI instance without
     raising.
  2. ``api.bridge.CalculusAPI.capacity_test_slide`` returns a valid JSON
     envelope (the bridge instantiates and the capacity probe responds).
  3. Parser + solver + slide pipeline renders one fixed curriculum slide
     end-to-end via the persistent subprocess worker.

Exits 0 on success, non-zero on first failure. Prints a one-line PASS or
FAIL summary per check plus a final aggregated verdict. Designed to be
wired into CI as a single command.

The script keeps imports inside each check so a missing optional
dependency surfaces as a localized failure (e.g., missing chromadb does
not poison the parser/solver checks).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Callable

# Allow running ``python scripts/smoke_test.py`` from any working directory:
# the project root must be on sys.path so ``import api.bridge`` resolves.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


_PASS = "PASS"
_FAIL = "FAIL"


def _run(name: str, fn: Callable[[], None]) -> bool:
    start = time.monotonic()
    try:
        fn()
    except Exception:
        elapsed = (time.monotonic() - start) * 1000
        print(f"[{_FAIL}] {name}  ({elapsed:.0f} ms)")
        traceback.print_exc()
        return False
    elapsed = (time.monotonic() - start) * 1000
    print(f"[{_PASS}] {name}  ({elapsed:.0f} ms)")
    return True


def check_backend_app_constructs() -> None:
    """``ai_tutor.main.create_app`` returns a FastAPI instance."""
    from fastapi import FastAPI

    from ai_tutor.main import create_app

    app = create_app()
    if not isinstance(app, FastAPI):
        raise AssertionError(
            f"create_app() returned {type(app).__name__}, expected FastAPI"
        )


def check_bridge_capacity_probe() -> None:
    """``CalculusAPI.capacity_test_slide`` returns a valid JSON envelope.

    Uses ``__new__`` to avoid running the full constructor (which spawns
    the persistent render worker and writes a capacity report to disk).
    The capacity probe itself is a method-level shape check.
    """
    from api.bridge import CalculusAPI

    api = CalculusAPI.__new__(CalculusAPI)
    raw = api.capacity_test_slide(text="smoke", with_image=False, page_index=0)
    payload = json.loads(raw)
    if "success" not in payload:
        raise AssertionError(
            f"capacity probe envelope missing 'success' key: {payload!r}"
        )
    # Reason / error string is informational; we just assert the envelope
    # serializes cleanly and is structurally valid.
    json.dumps(payload)


def _teardown_render_worker(api) -> None:
    """Best-effort teardown of the persistent render worker subprocess.

    Sends SIGTERM, waits up to 5 s, then SIGKILL on timeout. All errors
    are warnings — a leaked daemon child is preferable to masking a real
    failure in the calling check.
    """
    worker = getattr(api, "_render_worker", None)
    if worker is None:
        return
    try:
        worker.terminate()
        try:
            worker.wait(timeout=5)
        except subprocess.TimeoutExpired:
            worker.kill()
            try:
                worker.wait(timeout=5)
            except subprocess.TimeoutExpired as exc:
                print(
                    f"[warn] render worker did not exit after kill: {exc}",
                    file=sys.stderr,
                )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"[warn] render worker teardown: {exc}", file=sys.stderr)


def check_render_pipeline() -> None:
    """Render one fixed curriculum slide end-to-end without WebView."""
    from api.bridge import CalculusAPI

    api = CalculusAPI()
    try:
        curriculum = json.loads(api.get_curriculum())
        pathways = curriculum.get("pathways") or []
        if not pathways:
            raise AssertionError("curriculum has no pathways")
        chapters = pathways[0].get("chapters") or []
        if not chapters:
            raise AssertionError("first pathway has no chapters")

        raw = api.render_learning_slide(
            pathways[0]["id"], chapters[0]["id"], 0
        )
        payload = json.loads(raw)
        if not payload.get("success"):
            raise AssertionError(
                f"render_learning_slide failed: {payload.get('error')!r}"
            )
        data_url = payload.get("data_url", "")
        if not isinstance(data_url, str) or not data_url.startswith(
            "data:image/png;base64,"
        ):
            raise AssertionError(
                f"unexpected data_url shape: {data_url[:60]!r}"
            )
    finally:
        _teardown_render_worker(api)


def main() -> int:
    checks = [
        ("backend_app_constructs", check_backend_app_constructs),
        ("bridge_capacity_probe", check_bridge_capacity_probe),
        ("render_pipeline", check_render_pipeline),
    ]
    print("Calculus Animator — smoke test")
    print("=" * 60)
    failures = 0
    for name, fn in checks:
        if not _run(name, fn):
            failures += 1
    print("=" * 60)
    if failures:
        print(f"FAIL ({failures} of {len(checks)} checks failed)")
        return 1
    print(f"PASS (all {len(checks)} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
