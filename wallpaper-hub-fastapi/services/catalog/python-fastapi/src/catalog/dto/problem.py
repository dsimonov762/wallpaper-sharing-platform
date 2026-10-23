"""RFC 9457 problem details (README 5.2)."""

from catalog.dto.base import ApiModel


class FieldErrorDto(ApiModel):
    field: str
    code: str
    message: str


class ProblemDetails(ApiModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str
    errors: list[FieldErrorDto] | None = None
