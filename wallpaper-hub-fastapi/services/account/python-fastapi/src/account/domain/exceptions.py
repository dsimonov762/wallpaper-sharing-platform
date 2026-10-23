"""Application exceptions (README section 5.3). One HTTP handler turns them into responses.

Domain code raises these; it never builds HTTP responses itself.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FieldIssue:
    """One problem with one input field, e.g. ("username", "AlreadyExists", "...")."""

    field: str
    code: str
    message: str  # English text, used when `message_key` is not set
    # Optional: a key from contracts/i18n plus its placeholder values. When set, the error
    # handler builds the message in the caller's language and `message` is only the fallback.
    message_key: str | None = None
    message_args: Mapping[str, Any] | None = None


class AppException(Exception):  # noqa: N818  (the README names this family *Exception)
    """Base class: every subclass carries its HTTP status and problem type."""

    status: int = 500
    problem: str = "internal-error"
    title: str = "Internal error"
    title_key: str = "error.internal.title"  # i18n key for `title`

    def __init__(
        self,
        detail: str,
        errors: Sequence[FieldIssue] = (),
        headers: Mapping[str, str] | None = None,
        *,
        message_key: str | None = None,
        message_args: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        # `detail` is the English text (also what logs show). If `message_key` is given, the
        # HTTP handler translates it instead and uses `detail` only as the fallback.
        self.detail = detail
        self.message_key = message_key
        self.message_args = dict(message_args or {})
        self.errors = list(errors)
        # Extra HTTP response headers the error handler should send, for example
        # `WWW-Authenticate` on a 401. Same idea as Starlette's own HTTPException.
        self.headers = dict(headers or {})


class ValidationException(AppException):
    status = 400
    problem = "validation-failed"
    title = "Validation failed"
    title_key = "error.validationFailed.title"


class ForbiddenException(AppException):
    """The caller is known but not allowed to do this (403)."""

    status = 403
    problem = "forbidden"
    title = "Access denied"
    title_key = "error.forbidden.title"


class NotFoundException(AppException):
    status = 404
    problem = "not-found"
    title = "Resource not found"
    title_key = "error.notFound.title"


class ConflictException(AppException):
    status = 409
    problem = "conflict"
    title = "Conflict"
    title_key = "error.conflict.title"


class UnauthorizedException(AppException):
    """No credentials, or credentials that do not check out (401)."""

    status = 401
    problem = "unauthorized"
    title = "Authentication required"
    title_key = "error.unauthorized.title"


class ServiceUnavailableException(AppException):
    """We cannot do the work right now, but the caller did nothing wrong (503)."""

    status = 503
    problem = "service-unavailable"
    title = "Service unavailable"
    title_key = "error.serviceUnavailable.title"


class PreconditionFailedException(AppException):
    """The caller's copy is out of date: someone else changed the resource first (412)."""

    status = 412
    problem = "precondition-failed"
    title = "Precondition failed"
    title_key = "error.preconditionFailed.title"


class PreconditionRequiredException(AppException):
    """The request must say which version it is based on, and did not (428)."""

    status = 428
    problem = "precondition-required"
    title = "Precondition required"
    title_key = "error.preconditionRequired.title"
