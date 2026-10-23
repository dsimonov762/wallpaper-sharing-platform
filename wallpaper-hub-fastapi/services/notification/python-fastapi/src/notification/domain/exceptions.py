"""Exception model (README section 5.3). One handler turns these into HTTP answers."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FieldViolation:
    """One invalid field: which field, a machine code (Required, Size, ...), a message."""

    field: str
    code: str
    message: str


class AppException(Exception):  # noqa: N818 - name fixed by README section 5.3
    """Base class. `code` becomes the problem type slug and later the i18n message key."""

    status: int = 500
    code: str = "internal-error"
    title: str = "Internal server error"
    default_detail: str | None = None

    def __init__(
        self,
        detail: str | None = None,
        *,
        errors: Iterable[FieldViolation] = (),
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.detail = detail or self.default_detail
        self.errors = tuple(errors)
        self.headers = dict(headers) if headers else {}
        super().__init__(self.detail or self.title)


class ValidationException(AppException):
    status = 400
    code = "validation-failed"
    title = "Validation failed"
    default_detail = "One or more fields are invalid."


class UnauthorizedException(AppException):
    status = 401
    code = "unauthorized"
    title = "Unauthorized"


class ForbiddenException(AppException):
    status = 403
    code = "forbidden"
    title = "Forbidden"


class NotFoundException(AppException):
    status = 404
    code = "not-found"
    title = "Resource not found"


class ConflictException(AppException):
    status = 409
    code = "conflict"
    title = "Conflict"


class ServiceUnavailableException(AppException):
    status = 503
    code = "service-unavailable"
    title = "Service unavailable"
