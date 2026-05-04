#!/usr/bin/env python3
"""Single entry point — verifies dependencies, then launches the app."""
# guardrails: allow-runtime-pip
# guardrails: allow-runtime-package-install
import argparse
import importlib
import importlib.util
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

if sys.platform == 'darwin':
    import multiprocessing
    multiprocessing.set_start_method('spawn', force=True)

_VERSION = "1.0.0"

_REQUIRED_PKGS = {
    "webview": "pywebview>=4.4",
    "sympy": "sympy>=1.12",
    "numpy": "numpy>=1.24",
    "pygame": "pygame>=2.5",
    "antlr4": "antlr4-python3-runtime==4.11.1",
}

_MIN_VERSIONS = {"sympy": (1, 12), "numpy": (1, 24)}

# The project logger is initialised inside ``main`` after ``ensure_deps``
# verifies the third-party stack. Helpers reference this module-level handle;
# they're only invoked from ``main`` so the lazy init is safe.
_logger = None


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description=(
            "Calculus Animator — desktop shell + AI tutor backend launcher."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Environment:\n"
            "  CALCULUS_ANIMATOR_AUTO_INSTALL=1   Auto-install missing pip deps\n"
            "  LLM_PROVIDER, OPENAI_API_KEY, ...  See .env.example for the full list\n"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"calculus-animator {_VERSION}",
    )
    return parser


def _warn_old_version(name: str, ver_str: str, min_ver: tuple) -> None:
    parts = tuple(int(x) for x in ver_str.split(".")[:2] if x.isdigit())
    if parts and parts < min_ver:
        print(
            f"[warn] {name} {ver_str} is older than required "
            f"{'.'.join(str(v) for v in min_ver)}. Some features may not "
            f"work correctly.",
            file=sys.stderr,
        )


def _check_versions() -> None:
    try:
        import sympy
        ver = getattr(sympy, "__version__", "") or ""
        _warn_old_version("sympy", ver, _MIN_VERSIONS["sympy"])
    except (ImportError, AttributeError, ValueError) as exc:
        if _logger is not None:
            _logger.debug("sympy version-check skipped: %s", exc)

    try:
        import numpy
        ver = getattr(numpy, "__version__", "") or ""
        _warn_old_version("numpy", ver, _MIN_VERSIONS["numpy"])
    except (ImportError, AttributeError, ValueError) as exc:
        if _logger is not None:
            _logger.debug("numpy version-check skipped: %s", exc)


def _module_installed(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def ensure_deps() -> None:
    missing = [pkg for mod, pkg in _REQUIRED_PKGS.items() if not _module_installed(mod)]
    if missing:
        if os.environ.get("CALCULUS_ANIMATOR_AUTO_INSTALL") != "1":
            print(
                f"Missing required packages: {', '.join(missing)}\n"
                "Install them manually with:\n"
                f"  pip install {' '.join(missing)}\n"
                "Or set CALCULUS_ANIMATOR_AUTO_INSTALL=1 to auto-install.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"Installing missing packages: {', '.join(missing)}")
        # guardrails: allow-runtime-pip
        # guardrails: allow-runtime-package-install
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing, "-q"])
    _check_versions()


_PROJECT_ROOT = Path(__file__).parent.resolve()
_LOCAL_ENV = (_PROJECT_ROOT / ".env").resolve()


def _load_env() -> None:
    if _LOCAL_ENV.exists():
        for candidate in (_LOCAL_ENV,):
            try:
                candidate.relative_to(_PROJECT_ROOT)
            except ValueError:
                if _logger is not None:
                    _logger.warning(
                        "Skipping .env outside project root: %s", candidate
                    )
                continue
            with open(candidate) as f:
                for raw in f:
                    line = raw.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        os.environ.setdefault(k.strip(), v.strip())

    if os.environ.get("DEEPSEEK_API_KEY"):
        os.environ.setdefault("LLM_PROVIDER", "deepseek")
    elif os.environ.get("GOOGLE_API_KEY"):
        os.environ.setdefault("LLM_PROVIDER", "google")
    else:
        import shutil
        if shutil.which("gemini"):
            os.environ.setdefault("LLM_PROVIDER", "gemini_cli")
        else:
            os.environ.setdefault("LLM_PROVIDER", "local")


def _drain_stream_to_logger(stream, label: str) -> None:
    """Forward backend subprocess stream lines to the project logger.

    Mirrors ``api.bridge._drain_stream_to_logger``. Prevents the OS pipe
    buffer from filling and silently masking startup failures.
    """
    if stream is None:
        return
    try:
        for line in iter(stream.readline, ""):
            text = line.rstrip()
            if text and _logger is not None:
                _logger.warning("[%s] %s", label, text)
    except (OSError, ValueError) as exc:
        if _logger is not None:
            _logger.debug("%s drain ended: %s", label, exc)
    finally:
        try:
            stream.close()
        except (OSError, ValueError) as exc:
            if _logger is not None:
                _logger.debug("%s close failed: %s", label, exc)


def _start_backend() -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "ai_tutor.main:app",
         "--host", "127.0.0.1", "--port", "8000", "--log-level", "warning"],
        cwd=_PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    threading.Thread(
        target=_drain_stream_to_logger,
        args=(proc.stderr, "ai-tutor"),
        name="ai-tutor-stderr-drain",
        daemon=True,
    ).start()
    return proc


def _wait_for_backend(url: str = "http://127.0.0.1:8000/health", timeout: float = 120) -> bool:
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except (OSError, ValueError) as exc:
            if _logger is not None:
                _logger.debug("backend not ready yet: %s", exc)
            time.sleep(0.5)
    print("[warn] AI Tutor backend did not respond in time — chat may not work.")
    return False


def main(argv=None) -> None:
    """Launch the desktop shell.

    Argparse runs first so ``--help`` and ``--version`` short-circuit
    before any side effect (no dep install, no backend spawn, no
    PyWebView launch).
    """
    _build_arg_parser().parse_args(argv)

    ensure_deps()

    # config is stdlib-only and lives at the project root next to this
    # launcher; deferred until ``ensure_deps`` has verified the rest of
    # the third-party stack.
    from config import get_logger
    global _logger
    _logger = get_logger("run")

    _load_env()

    backend_process = _start_backend()
    _wait_for_backend()

    def _shutdown(sig=None, frame=None) -> None:
        backend_process.terminate()
        backend_process.wait()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    from api.bridge import CalculusAPI
    from window import launch

    try:
        launch(CalculusAPI())
    finally:
        _shutdown()

if __name__ == "__main__":
    if sys.platform == 'darwin':
        import multiprocessing
        multiprocessing.freeze_support()
    main()
