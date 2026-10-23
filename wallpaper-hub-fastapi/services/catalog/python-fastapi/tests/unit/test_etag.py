import pytest

from catalog.api.http.etag import make_etag, parse_if_match
from catalog.domain.exceptions import (
    PreconditionFailedException,
    PreconditionRequiredException,
    ValidationException,
)


def test_make_etag_is_quoted_version() -> None:
    assert make_etag(3) == '"3"'


def test_parse_strong_tag() -> None:
    assert parse_if_match('"7"') == 7


def test_star_means_any_version() -> None:
    assert parse_if_match("*") is None


def test_missing_header_is_428() -> None:
    with pytest.raises(PreconditionRequiredException):
        parse_if_match(None)


def test_weak_tag_is_412() -> None:
    with pytest.raises(PreconditionFailedException):
        parse_if_match('W/"3"')


@pytest.mark.parametrize("value", ["3", '"abc"', '""', '"3', '"-1"'])
def test_malformed_is_400(value: str) -> None:
    with pytest.raises(ValidationException):
        parse_if_match(value)
