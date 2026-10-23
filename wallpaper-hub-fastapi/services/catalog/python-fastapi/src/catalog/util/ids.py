"""Id generation. ULIDs sort by creation time and are safe to expose in URLs."""

from collections.abc import Callable

from ulid import ULID

IdFactory = Callable[[], str]


def new_wallpaper_id() -> str:
    return f"wp_{ULID()}"
