"""Domain vocabulary for media: the allowed values of purpose and status (README sections 6.2, 10).

These enums are the single source of truth. The database CHECK constraints are generated from
them, so the code and the schema cannot drift apart.
"""

from enum import StrEnum


class MediaPurpose(StrEnum):
    """What an upload is for. Decides size limits and which variants are generated."""

    AVATAR = "AVATAR"
    BANNER = "BANNER"
    WALLPAPER = "WALLPAPER"


class MediaStatus(StrEnum):
    """Life cycle of an asset: PROCESSING -> READY, or PROCESSING -> REJECTED."""

    PROCESSING = "PROCESSING"
    READY = "READY"
    REJECTED = "REJECTED"
