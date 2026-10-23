"""MongoDB connection holder. One async client per process, created in the lifespan."""

import logging
from typing import Any

from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import PyMongoError

from catalog.config.settings import Settings
from catalog.domain.exceptions import ServiceUnavailableException

logger = logging.getLogger(__name__)


class MongoDatabase:
    def __init__(self, client: AsyncMongoClient[dict[str, Any]], name: str) -> None:
        self._client = client
        self._name = name

    @property
    def wallpapers(self) -> AsyncCollection[dict[str, Any]]:
        return self._client[self._name]["wallpapers"]

    async def ping(self) -> None:
        """Readiness check. Raises 503 when MongoDB cannot be reached."""
        try:
            await self._client[self._name].command("ping")
        except PyMongoError as exc:
            logger.warning("MongoDB ping failed: %s", exc)
            raise ServiceUnavailableException("The database is not reachable.") from exc

    async def close(self) -> None:
        await self._client.close()


def create_mongo_database(settings: Settings) -> MongoDatabase:
    # The client connects lazily, so the service starts even when MongoDB is still down.
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
        settings.mongodb_uri.get_secret_value(),
        tz_aware=True,
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
        appname="catalog-service",
    )
    return MongoDatabase(client, settings.mongodb_database)
