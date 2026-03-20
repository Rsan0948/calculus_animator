#!/usr/bin/env python3
"""Single entry point — auto-installs dependencies, then launches the app."""
import importlib
import subprocess
import sys

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

def main():
    from api.bridge import CalculusAPI
    from app_main import launch

    launch(CalculusAPI())

if __name__ == "__main__":
    main()
