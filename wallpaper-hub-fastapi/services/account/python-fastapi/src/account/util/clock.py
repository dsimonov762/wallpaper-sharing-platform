"""Time source. Tests can monkeypatch this one function instead of freezing the system clock."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)
