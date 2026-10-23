"""Health endpoint response."""

from typing import Literal

from notification.dto.base import ApiModel

Status = Literal["UP", "DOWN"]


class HealthResponse(ApiModel):
    status: Status
    checks: dict[str, Status] | None = None
