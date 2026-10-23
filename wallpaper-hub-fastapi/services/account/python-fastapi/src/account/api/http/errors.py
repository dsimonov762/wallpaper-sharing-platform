"""One place that turns every failure into an RFC 9457 `application/problem+json` response.

Texts (`title`, `detail`, `errors[].message`) are localized from the `Accept-Language` header
using the shared bundles in `contracts/i18n` (README section 5.2).
"""

import logging
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from account.domain.exceptions import AppException, FieldIssue
from account.i18n import get_bundles, resolve_locale, translate

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

# Errors raised by the framework itself (unknown URL, wrong method): (title key, detail key)
_FRAMEWORK_KEYS = {
    404: ("error.notFound.title", "error.notFound.detail"),
    405: ("error.methodNotAllowed.title", "error.methodNotAllowed.detail"),
}


def request_locale(request: Request) -> str:
    """The language for this response, from the `Accept-Language` request header."""
    return resolve_locale(request.headers.get("accept-language"))


def problem_response(
    request: Request,
    *,
    status: int,
    slug: str,
    title: str,
    detail: str,
    errors: list[FieldIssue] | None = None,
    headers: Mapping[str, str] | None = None,
    locale: str | None = None,
) -> JSONResponse:
    """Build the problem+json response. `title`, `detail` and the issues are already localized."""
    body: dict[str, Any] = {
        "type": f"{PROBLEM_TYPE_BASE}{slug}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
    }
    if errors:
        body["errors"] = [{"field": e.field, "code": e.code, "message": e.message} for e in errors]
    response_headers = dict(headers or {})
    if locale:
        response_headers["Content-Language"] = locale
    return JSONResponse(
        body, status_code=status, media_type=PROBLEM_MEDIA_TYPE, headers=response_headers or None
    )


def _localize_issue(issue: FieldIssue, locale: str) -> FieldIssue:
    """Replace the English fallback by the translated text when the issue carries a key."""
    if issue.message_key is None:
        return issue
    message = translate(issue.message_key, locale, **(issue.message_args or {}))
    return FieldIssue(field=issue.field, code=issue.code, message=message)


def _message_key_for(
    kind: str, field: str, context: Mapping[str, Any], text: str
) -> tuple[str, dict[str, Any]] | None:
    """Map a pydantic error type to (i18n key, placeholder values), or None if we have no key."""
    args: dict[str, Any] = {"field": field}
    if kind == "missing":
        return "validation.required", args
    if kind in {"string_too_short", "too_short"} and "min_length" in context:
        return "validation.size.min", {**args, "min": context["min_length"]}
    if kind in {"string_too_long", "too_long"} and "max_length" in context:
        return "validation.size.max", {**args, "max": context["max_length"]}
    if kind == "string_pattern_mismatch":
        return "validation.pattern", args
    if kind == "literal_error":
        return "validation.invalidValue", args
    if kind == "greater_than_equal" and "ge" in context:
        return "validation.range.min", {**args, "min": context["ge"]}
    if kind == "less_than_equal" and "le" in context:
        return "validation.range.max", {**args, "max": context["le"]}
    if kind == "int_parsing":
        return "validation.invalidType", args
    if kind == "uuid_parsing":
        return "validation.invalidFormat", args
    if kind == "json_invalid":
        return "validation.malformedJson", args
    if kind == "value_error" and "email" in text.lower():
        return "validation.email", args
    return None


def _issues_from_validation_error(error: RequestValidationError) -> list[FieldIssue]:
    issues: list[FieldIssue] = []
    for item in error.errors():
        kind = str(item["type"])
        location = item["loc"]  # e.g. ("body", "username") or ("query", "size")
        if kind == "json_invalid":
            field = "body"
        else:
            field = ".".join(str(part) for part in location[1:]) or str(location[0])
        text = str(item["msg"]).removeprefix("Value error, ")
        context: Mapping[str, Any] = item.get("ctx", {})
        if kind == "value_error" and "email" in text.lower():
            code = "Email"
        else:
            code = _VALIDATION_CODES.get(kind, "Invalid")
        found = _message_key_for(kind, field, context, text)
        if found is None:
            # No key for this kind of error (for example a custom validator): the English text
            # from pydantic is kept. A later step can give those validators their own keys.
            issues.append(FieldIssue(field=field, code=code, message=text))
        else:
            key, args = found
            issues.append(
                FieldIssue(
                    field=field,
                    code=code,
                    message=translate(key, "en", **args),  # English fallback
                    message_key=key,
                    message_args=args,
                )
            )
    return issues


def register_exception_handlers(app: FastAPI) -> None:
    # Fail fast: a missing or broken bundle stops the service at startup, not at the first error.
    get_bundles()

    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        locale = request_locale(request)
        if exc.message_key:
            detail = translate(exc.message_key, locale, **exc.message_args)
        else:
            detail = exc.detail
        return problem_response(
            request,
            status=exc.status,
            slug=exc.problem,
            title=translate(exc.title_key, locale),
            detail=detail,
            errors=[_localize_issue(issue, locale) for issue in exc.errors],
            headers=exc.headers or None,
            locale=locale,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        locale = request_locale(request)
        return problem_response(
            request,
            status=400,
            slug="validation-failed",
            title=translate("error.validationFailed.title", locale),
            detail=translate("error.validationFailed.detail", locale),
            errors=[_localize_issue(i, locale) for i in _issues_from_validation_error(exc)],
            locale=locale,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Raised by the framework itself: unknown URL (404), wrong method (405), ...
        locale = request_locale(request)
        phrase = HTTPStatus(exc.status_code).phrase
        slug = phrase.lower().replace(" ", "-")
        title, detail = phrase, str(exc.detail)
        keys = _FRAMEWORK_KEYS.get(exc.status_code)
        if keys is not None:
            title = translate(keys[0], locale)
            if detail == phrase:  # the framework default; a route's own message stays as written
                detail = translate(keys[1], locale)
        return problem_response(
            request,
            status=exc.status_code,
            slug=slug,
            title=title,
            detail=detail,
            headers=dict(exc.headers) if exc.headers else None,
            locale=locale,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Log everything for us, tell the client nothing about internals.
        logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        locale = request_locale(request)
        return problem_response(
            request,
            status=500,
            slug="internal-error",
            title=translate("error.internal.title", locale),
            detail=translate("error.internal.detail", locale),
            locale=locale,
        )
