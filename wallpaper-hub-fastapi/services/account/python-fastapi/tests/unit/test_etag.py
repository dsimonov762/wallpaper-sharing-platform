"""ETag / If-Match parsing: pure logic, no HTTP."""

import pytest

from account.api.http.etag import etag_for, parse_if_match
from account.domain.exceptions import PreconditionRequiredException, ValidationException


def test_etag_is_the_quoted_version() -> None:
    assert etag_for(3) == '"3"'


def test_missing_header_is_428() -> None:
    with pytest.raises(PreconditionRequiredException):
        parse_if_match(None)


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ('"3"', {3}),
        ('  "3"  ', {3}),
        ('"3", "4"', {3, 4}),
        ('"3","7","9"', {3, 7, 9}),
        ('W/"3"', set[int]()),  # weak tags never match If-Match
        ('W/"3", "4"', {4}),
        ('"abc"', set[int]()),  # not one of our versions
        ('""', set[int]()),
        ('"' + "9" * 40 + '"', set[int]()),  # absurdly long numbers are ignored, not parsed
    ],
)
def test_strong_numeric_tags_become_accepted_versions(header: str, expected: set[int]) -> None:
    assert parse_if_match(header) == frozenset(expected)


@pytest.mark.parametrize("header", ["*", " * "])
def test_star_means_any_version(header: str) -> None:
    assert parse_if_match(header) is None


@pytest.mark.parametrize("header", ["", "3", "abc", '"3" "4"', '"3",', '*, "3"', '"3', "W/3"])
def test_malformed_headers_are_400(header: str) -> None:
    with pytest.raises(ValidationException) as info:
        parse_if_match(header)
    assert info.value.errors[0].field == "If-Match"
