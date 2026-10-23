import pytest

from account.domain.exceptions import ValidationException
from account.util.pagination import SortSpec, parse_sort, total_pages

ALLOWED = {"createdAt", "username"}


def test_parse_sort_with_direction() -> None:
    assert parse_sort("createdAt,desc", ALLOWED) == SortSpec("createdAt", descending=True)


def test_parse_sort_defaults_to_ascending() -> None:
    assert parse_sort("username", ALLOWED) == SortSpec("username", descending=False)


@pytest.mark.parametrize("raw", ["password,asc", "created_at,desc", "", "username,sideways"])
def test_parse_sort_rejects_unknown_field_or_direction(raw: str) -> None:
    with pytest.raises(ValidationException) as caught:
        parse_sort(raw, ALLOWED)

    assert caught.value.errors[0].field == "sort"


@pytest.mark.parametrize(
    ("total", "size", "expected"),
    [(0, 20, 0), (1, 20, 1), (20, 20, 1), (21, 20, 2), (101, 100, 2)],
)
def test_total_pages(total: int, size: int, expected: int) -> None:
    assert total_pages(total, size) == expected
