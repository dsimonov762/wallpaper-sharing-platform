"""Strong ETags for optimistic locking (README 5.2). The tag is the document version in quotes."""

from catalog.domain.exceptions import (
    FieldError,
    PreconditionFailedException,
    PreconditionRequiredException,
    ValidationException,
)


def make_etag(version: int) -> str:
    return f'"{version}"'


def parse_if_match(header: str | None, current_version: int | None = None) -> int | None:
    """Return the expected version, or None for '*'.

    Missing header -> 428. Malformed -> 400. Weak validator (W/"3") -> 412, because weak tags
    must not be used for If-Match (RFC 9110 13.1.1).
    """
    if header is None or not header.strip():
        raise PreconditionRequiredException("This request needs an If-Match header.")
    value = header.strip()
    if value == "*":
        return None
    if value.startswith("W/"):
        raise PreconditionFailedException("Weak ETags cannot be used with If-Match.")
    if len(value) >= 3 and value[0] == '"' and value[-1] == '"' and value[1:-1].isdecimal():
        return int(value[1:-1])
    raise ValidationException(
        "The If-Match header is malformed.",
        errors=[
            FieldError("If-Match", "InvalidFormat", 'Expected a quoted version like "3" or *.')
        ],
    )
