"""RFC 9457 problem+json body (README section 5.2)."""

from notification.dto.base import ApiModel


class FieldError(ApiModel):
    field: str
    code: str
    message: str


class ProblemDetail(ApiModel):
    type: str
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    errors: list[FieldError] | None = None
