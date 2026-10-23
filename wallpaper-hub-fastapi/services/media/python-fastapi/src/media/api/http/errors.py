"""One place that turns every failure into an RFC 9457 `application/problem+json` response."""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from media.domain.exceptions import AppException, FieldIssue

logger = logging.getLogger(__name__)

PROBLEM_MEDIA_TYPE = "application/problem+json"
PROBLEM_TYPE_BASE = "https://wallpaperhub.dev/problems/"

# pydantic error type -> the short, stable codes clients can switch on (README example: NotBlank)
_VALIDATION_CODES = {
    "missing": "Required",
    "string_too_short": "Size",
    "string_too_long": "Size",
    "too_short": "Size",  # lists and SecretStr use these names instead
    "too_long": "Size",
    "string_pattern_mismatch": "Pattern",
    "literal_error": "InvalidValue",
    "greater_than_equal": "Range",
    "less_than_equal": "Range",
    "int_parsing": "InvalidType",
    "uuid_parsing": "InvalidFormat",
    "json_invalid": "MalformedJson",
}


def problem_response(
    request: Request,
    *,
    status: int,
    slug: str,
    title: str,
    detail: str,
    errors: list[FieldIssue] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"{PROBLEM_TYPE_BASE}{slug}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
    }
    if errors:
        body["errors"] = [{"field": e.field, "code": e.code, "message": e.message} for e in errors]
    return JSONResponse(body, status_code=status, media_type=PROBLEM_MEDIA_TYPE, headers=headers)


def _issues_from_validation_error(error: RequestValidationError) -> list[FieldIssue]:
    issues: list[FieldIssue] = []
    for item in error.errors():
        kind = str(item["type"])
        location = item["loc"]  # e.g. ("body", "purpose") or ("query", "size")
        if kind == "json_invalid":
            field = "body"
        else:
            field = ".".join(str(part) for part in location[1:]) or str(location[0])
        message = str(item["msg"]).removeprefix("Value error, ")
        context = item.get("ctx", {})
        if kind == "too_short" and "min_length" in context:
            message = f"Must be at least {context['min_length']} characters long."
        elif kind == "too_long" and "max_length" in context:
            message = f"Must be at most {context['max_length']} characters long."
        code = _VALIDATION_CODES.get(kind, "Invalid")
        issues.append(FieldIssue(field=field, code=code, message=message))
    return issues


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        return problem_response(
            request,
            status=exc.status,
            slug=exc.problem,
            title=exc.title,
            detail=exc.detail,
            errors=exc.errors,
            headers=exc.headers or None,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return problem_response(
            request,
            status=400,
            slug="validation-failed",
            title="Validation failed",
            detail="One or more fields are invalid.",
            errors=_issues_from_validation_error(exc),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Raised by the framework itself: unknown URL (404), wrong method (405), ...
        phrase = HTTPStatus(exc.status_code).phrase
        slug = phrase.lower().replace(" ", "-")
        return problem_response(
            request,
            status=exc.status_code,
            slug=slug,
            title=phrase,
            detail=str(exc.detail),
            headers=dict(exc.headers) if exc.headers else None,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Log everything for us, tell the client nothing about internals.
        logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        return problem_response(
            request,
            status=500,
            slug="internal-error",
            title="Internal error",
            detail="An unexpected error occurred.",
        )
