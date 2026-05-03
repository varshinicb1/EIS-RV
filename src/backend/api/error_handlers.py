"""
Global error handlers and helpers for the FastAPI app.

Goal: never leak stack traces / internal paths / DB schema to the client.
Instead, log the full exception server-side with a short ``error_id`` and
return a sanitized JSON body containing only that id and a generic message.

Routes that want to surface a *specific* error to the user (4xx) should
still raise ``HTTPException`` directly with a safe message — those are
not touched by this module.

Usage::

    from src.backend.api.error_handlers import (
        install_error_handlers,
        internal_error,
    )

    app = FastAPI()
    install_error_handlers(app)

    @router.post("/foo")
    async def foo():
        try:
            ...
        except SomeKnownError as e:
            raise HTTPException(400, str(e))   # safe, user-facing
        except Exception as e:                  # unknown — log + sanitize
            raise internal_error(e, op="foo")
"""

from __future__ import annotations

import logging
import secrets
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("raman.errors")

_GENERIC_MESSAGE = (
    "An internal error occurred. Please retry; if it persists, contact "
    "support@vidyuthlabs.co.in with the error_id below."
)


def _new_error_id() -> str:
    return secrets.token_hex(6)


def internal_error(
    exc: BaseException,
    *,
    op: str,
    extra: Optional[dict[str, Any]] = None,
) -> HTTPException:
    """
    Log ``exc`` with full traceback under ``op`` context, and return a
    safe ``HTTPException(500)`` carrying only an opaque error_id.

    Caller pattern is ``raise internal_error(e, op="eis.simulate")``.
    """
    error_id = _new_error_id()
    logger.exception(
        "internal_error op=%s error_id=%s extra=%s",
        op,
        error_id,
        extra or {},
    )
    return HTTPException(
        status_code=500,
        detail={
            "code": "internal_error",
            "error_id": error_id,
            "op": op,
            "message": _GENERIC_MESSAGE,
        },
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Last-resort handler for anything that escapes a route. We do NOT echo
    ``str(exc)`` because Python exception messages frequently contain file
    paths, SQL fragments, and internal context.
    """
    error_id = _new_error_id()
    logger.exception(
        "unhandled_exception path=%s method=%s error_id=%s",
        request.url.path,
        request.method,
        error_id,
    )
    return JSONResponse(
        status_code=500,
        content={
            "code": "internal_error",
            "error_id": error_id,
            "message": _GENERIC_MESSAGE,
        },
    )


async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Pass-through for explicit ``HTTPException``s, but log 5xx ones with an
    error_id so support can correlate. 4xx are user-facing and don't get
    logged at error level.
    """
    if exc.status_code >= 500:
        error_id = _new_error_id()
        logger.error(
            "http_5xx path=%s method=%s status=%s error_id=%s detail=%r",
            request.url.path,
            request.method,
            exc.status_code,
            error_id,
            exc.detail,
        )
        # Sanitize: drop the original detail (may contain str(e))
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": "internal_error",
                "error_id": error_id,
                "message": _GENERIC_MESSAGE,
            },
        )
    # 4xx — preserve detail, since it's expected to be safe & actionable.
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def install_error_handlers(app: FastAPI) -> None:
    """Wire the handlers into the app. Call once during startup."""
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
