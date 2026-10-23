"""RFC 9457 problem details, used here to document error responses in OpenAPI."""

from account.dto.base import ApiModel


class FieldError(ApiModel):
    field: str
    code: str
    message: str


class ProblemDetail(ApiModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str
    errors: list[FieldError] | None = None
