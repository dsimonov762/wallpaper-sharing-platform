"""ETag and If-Match helpers (RFC 9110, sections 8.8.3 and 13.1.1).

An ETag is a label for one exact version of a resource. We build it from the `version`
column: version 3 becomes the header value `"3"` (the quotes are part of the format).

The client sends the label back in `If-Match` when it edits: "apply this change only if the
resource is still the version I looked at". That is optimistic locking over HTTP, and it
prevents the "lost update" where two people edit at once and the second silently erases the first.
"""

import re

from account.domain.exceptions import (
    FieldIssue,
    PreconditionRequiredException,
    ValidationException,
)

_TAG = r'(?:W/)?"[^"]*"'
_IF_MATCH = re.compile(rf"\s*(?:\*|{_TAG}(?:\s*,\s*{_TAG})*)\s*")
_ONE_TAG = re.compile(rf"{_TAG}")
_MAX_VERSION_DIGITS = 9


def etag_for(version: int) -> str:
    return f'"{version}"'


def parse_if_match(header: str | None) -> frozenset[int] | None:
    """Turn an `If-Match` header into the versions it accepts.

    Returns None for `*` ("any version, as long as the resource exists"), otherwise the set
    of accepted versions. Weak tags (`W/"3"`) never count: If-Match needs a strong match.

    Raises PreconditionRequiredException (428) when the header is missing and
    ValidationException (400) when it is not a valid If-Match value.
    """
    if header is None:
        raise PreconditionRequiredException(
            "This request must include an If-Match header with the ETag from a previous GET."
        )
    if _IF_MATCH.fullmatch(header) is None:
        raise ValidationException(
            "The If-Match header is malformed.",
            [FieldIssue("If-Match", "InvalidFormat", 'Expected an ETag such as "3", or *.')],
        )
    if header.strip() == "*":
        return None
    versions: set[int] = set()
    for tag in _ONE_TAG.findall(header):
        if tag.startswith("W/"):
            continue
        opaque = tag[1:-1]
        if opaque.isascii() and opaque.isdecimal() and len(opaque) <= _MAX_VERSION_DIGITS:
            versions.add(int(opaque))
    return frozenset(versions)
