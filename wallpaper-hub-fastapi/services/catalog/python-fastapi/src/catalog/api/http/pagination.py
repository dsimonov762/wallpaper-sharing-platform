"""?page=0&size=20&sort=createdAt,desc with a per-endpoint sort whitelist (README 5.2)."""

from collections.abc import Callable, Sequence
from typing import Annotated, cast, get_args

from fastapi import Query

from catalog.domain.exceptions import FieldError, ValidationException
from catalog.domain.ports import PageRequest, SortDirection, SortField

MAX_SIZE = 100
DEFAULT_SIZE = 20
WALLPAPER_SORT_FIELDS: tuple[SortField, ...] = get_args(SortField)


def total_pages(total_items: int, size: int) -> int:
    return -(-total_items // size)  # ceiling division without floats


def parse_sort(value: str, allowed: Sequence[SortField]) -> tuple[SortField, SortDirection]:
    name, _, direction = value.partition(",")
    direction = direction or "asc"
    if name not in allowed or direction not in {"asc", "desc"}:
        raise ValidationException(
            "The sort parameter is not valid.",
            errors=[
                FieldError(
                    "sort",
                    "InvalidValue",
                    f"Use <field>,<asc|desc> with one of: {', '.join(allowed)}.",
                )
            ],
        )
    return cast(SortField, name), cast(SortDirection, direction)


def page_params(
    allowed: Sequence[SortField], default_sort: str = "createdAt,desc"
) -> Callable[..., PageRequest]:
    """Build a FastAPI dependency for one endpoint."""

    def dependency(
        page: Annotated[int, Query(ge=0)] = 0,
        size: Annotated[int, Query(ge=1)] = DEFAULT_SIZE,
        sort: Annotated[str, Query(max_length=60)] = default_sort,
    ) -> PageRequest:
        field, direction = parse_sort(sort, allowed)
        # README: size is capped at 100 (we clamp instead of rejecting).
        return PageRequest(
            page=page, size=min(size, MAX_SIZE), sort_field=field, direction=direction
        )

    return dependency
