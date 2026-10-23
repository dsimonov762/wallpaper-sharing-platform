"""Development stand-in for the account gRPC client (replaced in step C5)."""

from catalog.domain.models import Author


class LocalAuthorDirectory:
    """Invents a snapshot from the id. No network, no account-service needed."""

    async def get_author(self, user_id: str) -> Author:
        short = user_id[:8]
        return Author(
            id=user_id, username=f"user-{short}", display_name=f"User {short}", avatar_url=None
        )
