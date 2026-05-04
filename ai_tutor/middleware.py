"""Backend hardening middleware: request-ID, body-size limit, access log.

These middlewares assume the loopback-only deployment: the backend is bound
to ``127.0.0.1``, so the only attackers in scope are local processes that
have already landed code on the host. The middleware exists to keep
operator-visible debugging clean and to fail fast on programmer-error or
prompt-injection-driven over-large payloads, not to enforce a network
perimeter.

Layered ASGI middleware, applied outermost first by ``main.create_app``:

1. ``RequestIdMiddleware``  - sets ``request_id_var``; outermost so every
   downstream log line and 413 envelope carries the id.
2. ``AccessLogMiddleware``  - emits exactly one JSON access-log line per
   request after the response status is known.
3. ``MaxBodySizeMiddleware``- rejects oversized requests with HTTP 413 +
   the structured error envelope.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Optional

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ai_tutor.logging_config import REQUEST_ID_HEADER, request_id_var

logger = logging.getLogger(__name__)
_access_logger = logging.getLogger("ai_tutor.access")

_DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB


def get_max_request_bytes() -> int:
    """Return the configured max request body size, defaulting to 10 MiB.

    Reads the ``CALCANIM_MAX_REQUEST_BYTES`` env var; non-positive or
    non-integer values fall back to the default and are logged at WARNING
    so misconfiguration is visible in the structured log.
    """
    raw = os.getenv("CALCANIM_MAX_REQUEST_BYTES")
    if raw is None:
        return _DEFAULT_MAX_BYTES
    try:
        value = int(raw)
        if value <= 0:
            raise ValueError
    except ValueError:
        logger.warning(
            "Ignoring invalid CALCANIM_MAX_REQUEST_BYTES=%r; falling back to %d",
            raw,
            _DEFAULT_MAX_BYTES,
        )
        return _DEFAULT_MAX_BYTES
    return value


def _envelope_bytes(error_type: str, message: str, request_id: str) -> bytes:
    """Encode the standard error envelope for direct ASGI sends."""
    body = {
        "error": {
            "type": error_type,
            "message": message,
            "request_id": request_id,
        }
    }
    return json.dumps(body, ensure_ascii=False).encode("utf-8")


async def _send_413(send: Send, max_bytes: int, request_id: str) -> None:
    body = _envelope_bytes(
        "RequestEntityTooLarge",
        f"Request body exceeds {max_bytes} bytes",
        request_id,
    )
    await send({
        "type": "http.response.start",
        "status": 413,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            (
                REQUEST_ID_HEADER.lower().encode("ascii"),
                request_id.encode("ascii"),
            ),
        ],
    })
    await send({"type": "http.response.body", "body": body})


class RequestIdMiddleware:
    """Generate (or honour) ``X-Request-Id`` and bind it to the request context.

    Honours an inbound ``X-Request-Id`` header if present (so a parent process
    like the PyWebView bridge can propagate its own correlation id). Falls
    back to a fresh uuid4 hex string. The id is set on the
    ``request_id_var`` ContextVar for the duration of the request and
    echoed on the response as ``X-Request-Id``. The header is added only
    if an inner layer has not already set it (so ``MaxBodySizeMiddleware``
    can run standalone without relying on this wrapper).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming: Optional[str] = None
        for k, v in scope.get("headers", []):
            if k.decode("latin-1").lower() == REQUEST_ID_HEADER.lower():
                incoming = v.decode("latin-1").strip() or None
                break
        rid = incoming or uuid.uuid4().hex
        token = request_id_var.set(rid)
        header_key = REQUEST_ID_HEADER.lower().encode("ascii")

        async def add_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                already_set = any(
                    name.lower() == header_key for name, _ in headers
                )
                if not already_set:
                    headers.append((header_key, rid.encode("ascii")))
                    message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, add_header)
        finally:
            request_id_var.reset(token)


class MaxBodySizeMiddleware:
    """Enforce a max request body size at the ASGI layer.

    Two layers of defence:
    - Cheap path: reject up-front when ``Content-Length`` declares > limit.
    - Robust path: count streamed bytes; on overflow, return 413 if the
      app has not yet started its response, otherwise mark the response
      as poisoned so we don't double-send.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        rid = request_id_var.get()
        max_bytes = self.max_bytes

        for k, v in scope.get("headers", []):
            if k.decode("latin-1").lower() == "content-length":
                try:
                    declared = int(v.decode("latin-1"))
                except ValueError:
                    declared = -1
                if declared > max_bytes:
                    await _send_413(send, max_bytes, rid)
                    return
                break

        seen = 0
        too_large = False
        response_started = False

        async def capped_receive() -> Message:
            nonlocal seen, too_large
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                seen += len(body)
                if seen > max_bytes:
                    too_large = True
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal response_started
            if too_large and not response_started:
                response_started = True
                await _send_413(send, max_bytes, rid)
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        await self.app(scope, capped_receive, guarded_send)
        if too_large and not response_started:
            await _send_413(send, max_bytes, rid)


class AccessLogMiddleware:
    """Emit one structured JSON log line per HTTP request.

    Captures the response status from the inner stack, then logs ``request``
    with method/path/status_code/duration_ms/client extras. The
    ``RequestIdFilter`` adds ``request_id`` automatically.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "?")
        path = scope.get("path", "?")
        client_host: Optional[str] = None
        client = scope.get("client")
        if client:
            client_host = client[0]
        start = time.monotonic()
        captured_status = {"value": 500}

        async def capture(message: Message) -> None:
            if message["type"] == "http.response.start":
                captured_status["value"] = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, capture)
        finally:
            duration_ms = round((time.monotonic() - start) * 1000.0, 3)
            _access_logger.info(
                "request",
                extra={
                    "method": method,
                    "path": path,
                    "status_code": captured_status["value"],
                    "duration_ms": duration_ms,
                    "client": client_host,
                },
            )
