"""Stable Proxy Hub API error responses."""

from dataclasses import dataclass

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@dataclass
class HubError(Exception):
    """Expected API failure with a public code and message."""

    status_code: int
    code: str
    message: str
    headers: dict[str, str] | None = None


def request_id(request: Request) -> str:
    """Return the request identifier assigned by middleware."""
    return str(request.state.request_id)


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build the public error envelope."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id(request),
            }
        },
        headers=headers,
    )


async def hub_error_handler(request: Request, error: Exception) -> JSONResponse:
    """Render an expected Hub failure."""
    if not isinstance(error, HubError):
        raise error
    return error_response(
        request,
        error.status_code,
        error.code,
        error.message,
        error.headers,
    )


async def validation_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    """Render malformed input without exposing internal validation details."""
    if not isinstance(error, RequestValidationError):
        raise error
    return error_response(
        request,
        400,
        "invalid_request",
        "The request is malformed or contains invalid values.",
    )


async def unexpected_error_handler(
    request: Request,
    _error: Exception,
) -> JSONResponse:
    """Render an unexpected failure without leaking internals."""
    return error_response(
        request,
        500,
        "internal_error",
        "The request could not be completed.",
    )
