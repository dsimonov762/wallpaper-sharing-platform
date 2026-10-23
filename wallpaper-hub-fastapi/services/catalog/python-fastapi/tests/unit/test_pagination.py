import pytest

from catalog.api.http.pagination import WALLPAPER_SORT_FIELDS, parse_sort, total_pages
from catalog.domain.exceptions import ValidationException


@pytest.mark.parametrize(
    ("total", "size", "expected"), [(0, 20, 0), (1, 20, 1), (20, 20, 1), (21, 20, 2), (45, 10, 5)]
)
def test_total_pages(total: int, size: int, expected: int) -> None:
    assert total_pages(total, size) == expected


def test_parse_sort_with_direction() -> None:
    assert parse_sort("title,desc", WALLPAPER_SORT_FIELDS) == ("title", "desc")


def test_parse_sort_defaults_to_ascending() -> None:
    assert parse_sort("title", WALLPAPER_SORT_FIELDS) == ("title", "asc")


@pytest.mark.parametrize("value", ["password,asc", "title,sideways", "", "author.id,asc"])
def test_parse_sort_rejects_unknown_input(value: str) -> None:
    with pytest.raises(ValidationException):
        parse_sort(value, WALLPAPER_SORT_FIELDS)
