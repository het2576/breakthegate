"""One error shape for every failure (docs/PRD.md section 7):

    {"error": {"code": "...", "message": "...", "retry_after": 30}}

429 and 503 responses also carry a standard Retry-After header.
"""

import math
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_FIELD_NAMES = {"task": "Task", "command": "Command", "handle": "Handle"}


class ApiError(Exception):
    def __init__(
        self, status: int, code: str, message: str, *, retry_after: float | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after


def error_response(
    status: int, code: str, message: str, retry_after: float | None = None
) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message}
    headers: dict[str, str] = {}
    if retry_after is not None:
        seconds = max(1, math.ceil(retry_after))
        body["retry_after"] = seconds
        headers["Retry-After"] = str(seconds)
    return JSONResponse({"error": body}, status_code=status, headers=headers)


def _validation_message(exc: RequestValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "The request is not valid."
    first = errors[0]
    loc = [str(part) for part in first.get("loc", ()) if part not in ("body", "query", "header")]
    field = loc[-1] if loc else "request"
    name = _FIELD_NAMES.get(field, field)
    ctx: dict[str, Any] = first.get("ctx") or {}
    kind = first.get("type", "")
    if kind == "string_too_long":
        return f"{name} is too long. The limit is {ctx.get('max_length')} characters."
    if kind == "string_too_short":
        return f"{name} cannot be empty."
    if kind == "missing":
        return f"{name} is required."
    if kind == "value_error":
        return str(ctx.get("error") or first.get("msg", "The request is not valid."))
    return f"{name}: {first.get('msg', 'not valid')}."


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return error_response(exc.status, exc.code, exc.message, exc.retry_after)

    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, exc: RequestValidationError) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return error_response(422, "validation", _validation_message(exc))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_request: Request, exc: StarletteHTTPException) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        code = "not_found" if exc.status_code == 404 else "http_error"
        return error_response(exc.status_code, code, str(exc.detail))
