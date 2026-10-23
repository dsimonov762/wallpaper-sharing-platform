"""Domain exceptions (README section 5.3).

Domain code raises these; it never builds HTTP responses. One handler in
`api/http/errors.py` turns them into `application/problem+json`.
"""

from dataclasses import dataclass
from http import HTTPStatus


@dataclass(frozen=True, slots=True)
class FieldIssue:
    """One invalid field in a request: what is wrong, in a stable code plus a message."""

    field: str
    code: str
    message: str


class AppException(Exception):  # noqa: N818  (the README names it AppException)
    """Base class. Subclasses only set `status`, `problem` (URL slug) and `title`."""

    status: int = HTTPStatus.INTERNAL_SERVER_ERROR.value
    problem: str = "internal-error"
    title: str = "Internal error"

    def __init__(
        self,
        detail: str | None = None,
        *,
        errors: list[FieldIssue] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.detail = detail or self.title
        self.errors = errors or []
        self.headers = headers or {}  # extra response headers, e.g. WWW-Authenticate
        super().__init__(self.detail)


class ValidationException(AppException):
    status = HTTPStatus.BAD_REQUEST.value
    problem = "validation-failed"
    title = "Validation failed"


class UnauthorizedException(AppException):
    status = HTTPStatus.UNAUTHORIZED.value
    problem = "unauthorized"
    title = "Unauthorized"


class ForbiddenException(AppException):
    status = HTTPStatus.FORBIDDEN.value
    problem = "forbidden"
    title = "Forbidden"


class NotFoundException(AppException):
    status = HTTPStatus.NOT_FOUND.value
    problem = "not-found"
    title = "Not found"


class ConflictException(AppException):
    status = HTTPStatus.CONFLICT.value
    problem = "conflict"
    title = "Conflict"


class ServiceUnavailableException(AppException):
    status = HTTPStatus.SERVICE_UNAVAILABLE.value
    problem = "service-unavailable"
    title = "Service unavailable"
