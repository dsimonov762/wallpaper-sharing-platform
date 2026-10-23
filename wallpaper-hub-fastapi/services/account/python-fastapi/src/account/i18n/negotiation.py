"""Pick the response language from an `Accept-Language` header (RFC 9110 section 12.5.4)."""

SUPPORTED_LOCALES = ("en", "de", "es")
DEFAULT_LOCALE = "en"


def resolve_locale(header: str | None) -> str:
    """Return the best supported locale for the header, or the default.

    Example header: `de-AT,de;q=0.9,en;q=0.5`. Each entry is a language tag with an optional
    weight `q` (0 to 1, default 1). We try the entries from the highest weight down and match
    on the primary language only, so `de-AT` and `de-CH` both give `de`.
    """
    if not header:
        return DEFAULT_LOCALE
    candidates: list[tuple[float, int, str]] = []
    for position, part in enumerate(header.split(",")):
        tag, *params = (piece.strip() for piece in part.split(";"))
        if not tag:
            continue
        weight = 1.0
        for param in params:
            name, _, value = param.partition("=")
            if name.strip().lower() == "q":
                try:
                    weight = float(value)
                except ValueError:
                    weight = 0.0  # a broken weight: treat the entry as unusable
        if weight <= 0:  # q=0 means "not acceptable"
            continue
        # sort key: highest weight first, then the order the client wrote them in
        candidates.append((-weight, position, tag.lower()))
    for _, _, tag in sorted(candidates):
        if tag == "*":
            return DEFAULT_LOCALE
        primary = tag.split("-")[0]
        if primary in SUPPORTED_LOCALES:
            return primary
    return DEFAULT_LOCALE
