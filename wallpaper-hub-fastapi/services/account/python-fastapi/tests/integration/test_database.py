from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine

from account.repository.database import create_session_factory, database_is_reachable
from account.repository.models import UserEntity

pytestmark = pytest.mark.integration


async def test_database_is_reachable(engine: AsyncEngine) -> None:
    assert await database_is_reachable(engine)


def test_ready_endpoint_reports_up(client: TestClient) -> None:
    assert client.get("/health/ready").status_code == 200


async def test_user_can_be_written_and_read_back(engine: AsyncEngine) -> None:
    """Needs `just account-migrate` first. Everything is rolled back, so no data is left."""
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        user = UserEntity(
            id=uuid4(), username="it_roundtrip", email="it_rt@example.com", display_name="RT"
        )
        session.add(user)
        await session.flush()  # sends the INSERT, so the database applies its defaults

        loaded = await session.get(UserEntity, user.id)

        assert loaded is not None
        assert loaded.locale == "en"
        assert loaded.status == "ACTIVE"
        assert loaded.version == 1
        assert loaded.created_at is not None
        await session.rollback()
