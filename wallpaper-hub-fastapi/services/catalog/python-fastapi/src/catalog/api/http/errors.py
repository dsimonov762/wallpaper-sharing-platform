"""One set of exception handlers: everything becomes RFC 9457 application/problem+json."""

import logging
from collections.abc import Mapping, Sequence

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from catalog.domain.exceptions import AppException, FieldError
from catalog.dto.problem import FieldErrorDto, ProblemDetails

logger = logging.getLogger(__name__)
PROBLEM_BASE = "https://wallpaperhub.dev/problems/"
PROBLEM_JSON = "application/problem+json"

_CODE_BY_PYDANTIC_TYPE = {
    "missing": "Required",
    "string_too_short": "Size",
    "string_too_long": "Size",
    "too_short": "Size",
    "too_long": "Size",
    "string_pattern_mismatch": "Pattern",
    "greater_than": "Range",
    "greater_than_equal": "Range",
    "less_than": "Range",
    "less_than_equal": "Range",
    "json_invalid": "MalformedJson",
    "int_parsing": "InvalidFormat",
    "int_from_float": "InvalidFormat",
    "datetime_parsing": "InvalidFormat",
}


def problem_response(
    request: Request,
    *,
    status: int,
    slug: str,
    title: str,
    detail: str,
    errors: Sequence[FieldError] = (),
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ProblemDetails(
        type=f"{PROBLEM_BASE}{slug}",
        title=title,
        status=status,
        detail=detail,
        instance=request.url.path,
        errors=[FieldErrorDto(field=e.field, code=e.code, message=e.message) for e in errors]
        or None,
    )
    return JSONResponse(
        status_code=status,
        content=jsonable_encoder(body.model_dump(by_alias=True, exclude_none=True)),
        media_type=PROBLEM_JSON,
        headers=dict(headers or {}),
    )


def _field_name(loc: tuple[int | str, ...]) -> str:
    parts = loc[1:] if loc and loc[0] in {"body", "query", "path", "header"} else loc
    name = ""
    for part in parts:
        name += f"[{part}]" if isinstance(part, int) else (f".{part}" if name else part)
    return name or "body"


def _clean_message(message: str) -> str:
    return message.removeprefix("Value error, ")


async def _app_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppException)  # noqa: S101 - narrows the type for Pyright
    return problem_response(
        request,
        status=exc.status,
        slug=exc.slug,
        title=exc.title,
        detail=exc.detail,
        errors=exc.errors,
        headers=exc.headers,
    )


async def _validation_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    errors = [
        FieldError(
            field=_field_name(tuple(err["loc"])),
            code=_CODE_BY_PYDANTIC_TYPE.get(str(err["type"]), "InvalidValue"),
            message=_clean_message(str(err["msg"])),
        )
        for err in exc.errors()
    ]
    return problem_response(
        request,
        status=400,
        slug="validation-failed",
        title="Validation failed",
        detail="One or more fields are invalid.",
        errors=errors,
    )


async def _http_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    slugs = {404: "not-found", 405: "method-not-allowed"}
    return problem_response(
        request,
        status=exc.status_code,
        slug=slugs.get(exc.status_code, "http-error"),
        title="Not found" if exc.status_code == 404 else "Request error",
        detail=str(exc.detail),
        headers=exc.headers,
    )


async def _unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s", request.url.path, exc_info=exc)
    return problem_response(
        request,
        status=500,
        slug="internal-error",
        title="Internal error",
        detail="An unexpected error occurred.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, _app_exception)
    app.add_exception_handler(RequestValidationError, _validation_exception)
    app.add_exception_handler(StarletteHTTPException, _http_exception)
    app.add_exception_handler(Exception, _unexpected_exception)
