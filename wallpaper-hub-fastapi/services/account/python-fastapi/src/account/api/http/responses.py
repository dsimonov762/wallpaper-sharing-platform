"""Shared OpenAPI documentation for error responses."""

from typing import Any

from account.dto.problem import ProblemDetail

BAD_REQUEST: dict[int | str, dict[str, Any]] = {
    400: {"model": ProblemDetail, "description": "Validation failed"}
}
NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": ProblemDetail, "description": "Resource not found"}
}
CONFLICT: dict[int | str, dict[str, Any]] = {
    409: {"model": ProblemDetail, "description": "Conflict (already exists)"}
}
UNAUTHORIZED: dict[int | str, dict[str, Any]] = {
    401: {"model": ProblemDetail, "description": "Missing, invalid or expired access token"}
}
FORBIDDEN: dict[int | str, dict[str, Any]] = {
    403: {"model": ProblemDetail, "description": "Signed in, but not allowed to do this"}
}
PRECONDITION_FAILED: dict[int | str, dict[str, Any]] = {
    412: {"model": ProblemDetail, "description": "If-Match does not match the current version"}
}
PRECONDITION_REQUIRED: dict[int | str, dict[str, Any]] = {
    428: {"model": ProblemDetail, "description": "The If-Match header is required"}
}
