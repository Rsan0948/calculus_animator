from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from typing import Any, Callable

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _FallbackBenchmark:
    def __init__(self) -> None:
        self.stats = SimpleNamespace(stats=SimpleNamespace(median=0.0))

    def __call__(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        start = perf_counter()
        result = func(*args, **kwargs)
        elapsed = perf_counter() - start
        self.stats = SimpleNamespace(stats=SimpleNamespace(median=elapsed))
        return result


@pytest.fixture
def benchmark() -> _FallbackBenchmark:
    """Provide a minimal benchmark fixture when pytest-benchmark is unavailable."""
    return _FallbackBenchmark()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "benchmark: performance regression marker")
