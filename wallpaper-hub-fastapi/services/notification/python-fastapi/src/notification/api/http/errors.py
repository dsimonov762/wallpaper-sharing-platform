"""One set of exception handlers: every error leaves the service as problem+json."""

import http
import logging
from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from notification.domain.exceptions import AppException, FieldViolation
from notification.dto.problem import FieldError, ProblemDetail

logger = logging.getLogger(__name__)

PROBLEM_BASE_URL = "https://wallpaperhub.dev/problems/"
PROBLEM_MEDIA_TYPE = "application/problem+json"

_LOCATION_PREFIXES = {"body", "query", "path", "header", "cookie"}
_SIZE_TYPES = {"string_too_short", "string_too_long", "too_short", "too_long"}
_RANGE_TYPES = {
    "greater_than",
    "greater_than_equal",
    "less_than",
    "less_than_equal",
    "multiple_of",
}


def problem_response(
    request: Request,
    *,
    code: str,
    title: str,
    status: int,
    detail: str | None = None,
    errors: Sequence[FieldViolation] = (),
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ProblemDetail(
        type=f"{PROBLEM_BASE_URL}{code}",
        title=title,
        status=status,
        detail=detail,
        instance=request.url.path,
        errors=[FieldError(field=e.field, code=e.code, message=e.message) for e in errors] or None,
    )
    return JSONResponse(
        status_code=status,
        content=body.model_dump(mode="json", by_alias=True, exclude_none=True),
        media_type=PROBLEM_MEDIA_TYPE,
        headers=dict(headers) if headers else None,
    )


def _field_name(loc: Sequence[int | str], error_type: str) -> str:
    if error_type == "json_invalid":
        return "body"
    parts = list(loc)
    if parts and parts[0] in _LOCATION_PREFIXES:
        parts = parts[1:]
    name = ""
    for part in parts:
        if isinstance(part, int):
            name += f"[{part}]"
        else:
            name = f"{name}.{part}" if name else part
    return name or "body"


def _violation_code(error_type: str) -> str:
    if error_type == "missing":
        return "Required"
    if error_type == "json_invalid":
        return "MalformedJson"
    if error_type in _SIZE_TYPES:
        return "Size"
    if error_type == "string_pattern_mismatch":
        return "Pattern"
    if error_type in _RANGE_TYPES:
        return "Range"
    if error_type.endswith(("_parsing", "_type")):
        return "InvalidFormat"
    return "InvalidValue"


def _to_violations(errors: Sequence[Mapping[str, Any]]) -> list[FieldViolation]:
    return [
        FieldViolation(
            field=_field_name(error["loc"], error["type"]),
            code=_violation_code(error["type"]),
            message=str(error["msg"]),
        )
        for error in errors
    ]


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        if exc.status >= 500:
            logger.error("%s on %s %s", exc.code, request.method, request.url.path, exc_info=exc)
        return problem_response(
            request,
            code=exc.code,
            title=exc.title,
            status=exc.status,
            detail=exc.detail,
            errors=exc.errors,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # 400, not FastAPI's default 422 (README section 5.3). Never echo the input back.
        return problem_response(
            request,
            code="validation-failed",
            title="Validation failed",
            status=400,
            detail="One or more fields are invalid.",
            errors=_to_violations(exc.errors()),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        phrase = http.HTTPStatus(exc.status_code).phrase
        return problem_response(
            request,
            code=phrase.lower().replace(" ", "-"),
            title=phrase,
            status=exc.status_code,
            detail=None if exc.detail == phrase else str(exc.detail),
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        return problem_response(
            request,
            code="internal-error",
            title="Internal server error",
            status=500,
            detail="An unexpected error occurred.",
        )
