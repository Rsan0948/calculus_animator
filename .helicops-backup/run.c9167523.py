#!/usr/bin/env python3
"""Single entry point — auto-installs dependencies, then launches the app."""
import importlib
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# Fix for macOS multiprocessing 'spawn' causing double-launch
# Must be before any other imports that might trigger subprocess
if sys.platform == 'darwin':
    import multiprocessing
    multiprocessing.set_start_method('spawn', force=True)

REQUIRED = {
    "webview": "pywebview>=4.4",
    "sympy": "sympy>=1.12",
    "numpy": "numpy>=1.24",
    "pygame": "pygame>=2.5",
    "antlr4": "antlr4-python3-runtime==4.11.1",
}

# Minimum versions to warn about if the import check passes but the installed
# version is too old (importlib.import_module succeeds even for outdated installs).
_MIN_VERSIONS = {"sympy": (1, 12), "numpy": (1, 24)}


def _check_versions():
    for mod, min_ver in _MIN_VERSIONS.items():
        try:
            m = importlib.import_module(mod)
            ver_str = getattr(m, "__version__", "") or ""
            parts = tuple(int(x) for x in ver_str.split(".")[:2] if x.isdigit())
            if parts and parts < min_ver:
                print(
                    f"[warn] {mod} {ver_str} is older than required {'.'.join(str(v) for v in min_ver)}. "
                    f"Some features may not work correctly.",
                    file=sys.stderr,
                )
        except Exception:
            pass


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
    _check_versions()

ensure_deps()

_LOCAL_ENV = Path(__file__).parent / ".env"


def _load_env():
    # Load local .env (copy .env.example → .env and fill in your API keys)
    if _LOCAL_ENV.exists():
        with open(_LOCAL_ENV) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())

    # Smart provider selection
    if os.environ.get("DEEPSEEK_API_KEY"):
        os.environ.setdefault("LLM_PROVIDER", "deepseek")
    elif os.environ.get("GOOGLE_API_KEY"):
        os.environ.setdefault("LLM_PROVIDER", "google")
    else:
        # Check if gemini CLI is available
        import shutil
        if shutil.which("gemini"):
            os.environ.setdefault("LLM_PROVIDER", "gemini_cli")
        else:
            os.environ.setdefault("LLM_PROVIDER", "local")


def _start_backend():
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "ai_tutor.main:app",
         "--host", "127.0.0.1", "--port", "8000", "--log-level", "warning"],
        cwd=Path(__file__).parent,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True
    )


def _wait_for_backend(url="http://127.0.0.1:8000/health", timeout=120):
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    print("[warn] AI Tutor backend did not respond in time — chat may not work.")
    return False


def main():
    _load_env()

    backend_process = _start_backend()
    _wait_for_backend()

    def _shutdown(sig=None, frame=None):
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
    # Required for multiprocessing on macOS/Windows to prevent double-launch
    # when subprocesses are spawned
    if sys.platform == 'darwin':
        import multiprocessing
        multiprocessing.freeze_support()
    
    main()
