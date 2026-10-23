"""Domain exceptions. One global handler in api/http/errors.py turns them into problem+json."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FieldError:
    field: str
    code: str
    message: str


class AppException(Exception):  # noqa: N818 - name fixed by README 5.3
    status: int = 500
    slug: str = "internal-error"
    title: str = "Internal error"

    def __init__(
        self,
        detail: str,
        *,
        errors: Sequence[FieldError] = (),
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.errors = tuple(errors)
        self.headers = dict(headers or {})


class ValidationException(AppException):
    status = 400
    slug = "validation-failed"
    title = "Validation failed"


class NotFoundException(AppException):
    status = 404
    slug = "not-found"
    title = "Not found"


class PreconditionFailedException(AppException):
    status = 412
    slug = "precondition-failed"
    title = "Precondition failed"


class PreconditionRequiredException(AppException):
    status = 428
    slug = "precondition-required"
    title = "Precondition required"


class ServiceUnavailableException(AppException):
    status = 503
    slug = "service-unavailable"
    title = "Service unavailable"
