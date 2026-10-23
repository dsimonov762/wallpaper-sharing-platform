"""Conversions between layers: DTO -> domain command, entity -> response DTO.

Explicit field-by-field mapping on purpose: adding a column to the table can never leak
into the API by accident.
"""

from account.domain.user_service import ProfileChanges, Registration
from account.dto.user import (
    PublicUserResponse,
    RegistrationRequest,
    UpdateProfileRequest,
    UserResponse,
)
from account.repository.models import UserEntity


def to_registration(request: RegistrationRequest) -> Registration:
    return Registration(
        username=request.username,
        email=request.email,
        password=request.password,
        display_name=request.display_name,
        locale=request.locale,
    )


def to_profile_changes(request: UpdateProfileRequest) -> ProfileChanges:
    """Keep only what the client actually sent, so omitted fields are never overwritten."""
    sent = request.model_fields_set
    changes: ProfileChanges = {}
    if "display_name" in sent and request.display_name is not None:
        changes["display_name"] = request.display_name
    if "bio" in sent:
        changes["bio"] = request.bio
    if "locale" in sent and request.locale is not None:
        changes["locale"] = request.locale
    return changes


def to_public_user(user: UserEntity) -> PublicUserResponse:
    return PublicUserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        bio=user.bio,
        avatar_asset_id=user.avatar_asset_id,
        banner_asset_id=user.banner_asset_id,
        created_at=user.created_at,
    )


def to_user(user: UserEntity) -> UserResponse:
    return UserResponse(
        **to_public_user(user).model_dump(),
        email=user.email,
        locale=user.locale,
        status=user.status,
        updated_at=user.updated_at,
        version=user.version,
    )
