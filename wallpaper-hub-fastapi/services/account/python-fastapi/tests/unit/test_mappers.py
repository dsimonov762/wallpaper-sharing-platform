from datetime import UTC, datetime
from uuid import uuid4

from account.dto.user import RegistrationRequest
from account.mapper.user_mapper import to_public_user, to_registration, to_user
from account.repository.models import UserEntity


def make_entity() -> UserEntity:
    now = datetime.now(UTC)
    return UserEntity(
        id=uuid4(),
        username="alice",
        email="alice@example.com",
        display_name="Alice",
        bio=None,
        locale="en",
        avatar_asset_id=None,
        banner_asset_id=None,
        status="ACTIVE",
        created_at=now,
        updated_at=now,
        version=1,
    )


def test_public_user_has_no_private_fields() -> None:
    payload = to_public_user(make_entity()).model_dump(by_alias=True)

    assert "email" not in payload
    assert "status" not in payload
    assert payload["displayName"] == "Alice"  # camelCase in JSON


def test_full_user_includes_email_and_status() -> None:
    payload = to_user(make_entity()).model_dump(by_alias=True)

    assert payload["email"] == "alice@example.com"
    assert payload["status"] == "ACTIVE"


def test_registration_request_is_normalized_and_mapped() -> None:
    request = RegistrationRequest.model_validate(
        {"username": "alice", "email": "  Alice@Example.COM ", "password": "correct-horse-battery"}
    )

    registration = to_registration(request)

    assert registration.email == "alice@example.com"
    assert registration.locale == "en"
    assert registration.password.get_secret_value() == "correct-horse-battery"
