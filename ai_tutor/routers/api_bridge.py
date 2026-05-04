"""HTTP shim around ``api.bridge.CalculusAPI`` for the Docker Space build.

Mirrors the JS-callable surface of the PyWebView desktop bridge so the
browser-side ``ui/js/modules/space_bridge.js`` (Lane B) can call the same
methods over ``fetch`` without a PyWebView shell. Each handler delegates
to the singleton ``CalculusAPI`` instance and parse-and-re-emits the JSON
string the bridge already returns.

Singleton lifecycle:
    The full ``CalculusAPI()`` constructor spawns the persistent slide
    render worker and loads curriculum / library / glossary data — that's
    expensive enough that we don't want it on app import (which would
    delay ``/health`` / ``/ready`` and cold-start every Space rebuild).
    Instead we lazily instantiate on the first ``/api/*`` request behind
    a ``threading.Lock``: the first request blocks ~1–2 s while the
    constructor runs, every subsequent request hits the cached instance.

Slide-render note:
    ``pygame`` is intentionally absent from the Space requirements.txt
    in this v1 cut, so ``/api/render_learning_slide`` and
    ``/api/capacity_test_slide`` will surface ``ModuleNotFoundError``
    via the global exception envelope. The Dockerfile already installs
    the SDL2 runtime so re-enabling those endpoints later only requires
    a one-line ``pygame==…`` addition to ``requirements.txt``.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

_api_singleton: Optional[Any] = None
_api_lock = threading.Lock()


def _get_api() -> Any:
    """Return the lazy ``CalculusAPI`` singleton.

    Double-checked locking with a module-level ``threading.Lock`` so
    concurrent first requests don't construct two instances (each of
    which would spawn its own render-worker subprocess).
    """
    global _api_singleton
    if _api_singleton is None:
        with _api_lock:
            if _api_singleton is None:
                # Imported here so the FastAPI app can boot in environments
                # where ``api.bridge`` import has slow side effects (curriculum
                # parse, capacity report write) — the cost is paid on the
                # first ``/api/*`` request, not at module load.
                from api.bridge import CalculusAPI

                _api_singleton = CalculusAPI()
                logger.info("CalculusAPI singleton constructed for /api/* shim")
    return _api_singleton


def _parse(raw: str) -> Any:
    """Parse a JSON string emitted by a bridge method back into a dict.

    Bridge methods historically return JSON-as-string for the PyWebView
    transport. The HTTP shim re-emits that as a JSON response body, which
    FastAPI re-serialises — so we parse first to avoid a double-encoded
    string showing up in the browser.
    """
    return json.loads(raw)


# ─────────────────────────────────────────────────────────────────────────────
# Request models
# ─────────────────────────────────────────────────────────────────────────────


class SolveRequest(BaseModel):
    latex_str: str = Field(..., description="LaTeX expression to solve.")
    calc_type: Optional[str] = Field(
        None,
        description="Optional explicit operation tag (derivative / integral / …).",
    )
    params: str = Field(
        "{}",
        description="JSON string of operation parameters; defaults to ``{}``.",
    )


class GraphDataRequest(BaseModel):
    latex_str: str
    calc_type: Optional[str] = None
    params: str = "{}"
    x_min: float = -10.0
    x_max: float = 10.0


class RenderSlideRequest(BaseModel):
    pathway_id: str
    chapter_id: str
    slide_index: int
    width: int = 1100
    height: int = 620


class CapacityTestRequest(BaseModel):
    text: str
    with_image: bool = False
    page_index: int = 0
    width: int = 1300
    height: int = 812


class LogRequest(BaseModel):
    msg: str
    level: str = "info"


# ─────────────────────────────────────────────────────────────────────────────
# Handlers — POST methods (state-changing or rich-arg shape)
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/solve")
async def solve(req: SolveRequest, api: Any = Depends(_get_api)) -> Any:
    return _parse(api.solve(req.latex_str, req.calc_type, req.params))


@router.post("/get_graph_data")
async def get_graph_data(
    req: GraphDataRequest, api: Any = Depends(_get_api)
) -> Any:
    return _parse(
        api.get_graph_data(
            req.latex_str, req.calc_type, req.params, req.x_min, req.x_max
        )
    )


@router.post("/render_learning_slide")
async def render_learning_slide(
    req: RenderSlideRequest, api: Any = Depends(_get_api)
) -> Any:
    return _parse(
        api.render_learning_slide(
            req.pathway_id, req.chapter_id, req.slide_index, req.width, req.height
        )
    )


@router.post("/capacity_test_slide")
async def capacity_test_slide(
    req: CapacityTestRequest, api: Any = Depends(_get_api)
) -> Any:
    return _parse(
        api.capacity_test_slide(
            req.text, req.with_image, req.page_index, req.width, req.height
        )
    )


@router.post("/log_to_python")
async def log_to_python(
    req: LogRequest, api: Any = Depends(_get_api)
) -> dict:
    """Forward a JS-side log line to the Python logger and ack."""
    api.log_to_python(req.msg, req.level)
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────────
# Handlers — GET methods (idempotent reference-data fetches)
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/get_formulas")
async def get_formulas(api: Any = Depends(_get_api)) -> Any:
    return _parse(api.get_formulas())


@router.get("/get_symbols")
async def get_symbols(api: Any = Depends(_get_api)) -> Any:
    return _parse(api.get_symbols())


@router.get("/get_demo_problems")
async def get_demo_problems(api: Any = Depends(_get_api)) -> Any:
    return _parse(api.get_demo_problems())


@router.get("/get_curriculum")
async def get_curriculum(api: Any = Depends(_get_api)) -> Any:
    return _parse(api.get_curriculum())


@router.get("/get_glossary")
async def get_glossary(api: Any = Depends(_get_api)) -> Any:
    return _parse(api.get_glossary())


@router.get("/get_learning_library")
async def get_learning_library(api: Any = Depends(_get_api)) -> Any:
    return _parse(api.get_learning_library())
