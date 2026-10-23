"""Pagination and sorting helpers shared by every list endpoint (README section 5.2)."""

import math
from collections.abc import Collection
from dataclasses import dataclass

from account.domain.exceptions import FieldIssue, ValidationException

MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class SortSpec:
    field: str
    descending: bool


@dataclass(frozen=True)
class PageResult[T]:
    """What a repository/service returns for one page; routers wrap it into the JSON envelope."""

    items: list[T]
    total: int


def total_pages(total_items: int, size: int) -> int:
    return math.ceil(total_items / size) if total_items else 0


def parse_sort(raw: str, allowed: Collection[str]) -> SortSpec:
    """Parse `createdAt,desc`. Only whitelisted fields are accepted (never raw column names)."""
    field, _, direction = (part.strip() for part in raw.partition(","))
    direction = direction.lower() or "asc"
    if field not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise ValidationException(
            "Invalid sort parameter.",
            [FieldIssue("sort", "InvalidValue", f"Sort field must be one of: {allowed_list}.")],
        )
    if direction not in {"asc", "desc"}:
        raise ValidationException(
            "Invalid sort parameter.",
            [FieldIssue("sort", "InvalidValue", "Sort direction must be 'asc' or 'desc'.")],
        )
    return SortSpec(field=field, descending=direction == "desc")
