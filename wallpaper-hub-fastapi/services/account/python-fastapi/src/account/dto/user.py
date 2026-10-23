"""User request/response models with their validation rules."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, EmailStr, Field, SecretStr, field_validator

from account.dto.base import ApiModel

USERNAME_PATTERN = r"^[a-z0-9_]{3,30}$"


class RegistrationRequest(ApiModel):
    # Pydantic merges this with ApiModel's config (camelCase aliases stay active).
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(pattern=USERNAME_PATTERN, description="3-30 chars: a-z, 0-9, underscore")
    email: EmailStr
    # SecretStr: never printed in logs, repr() or error output.
    password: SecretStr = Field(min_length=12, max_length=128)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    locale: Literal["en", "de", "es"] = "en"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if len(value) > 254:
            raise ValueError("email must be at most 254 characters")
        return value.lower()


class UpdateProfileRequest(ApiModel):
    """PATCH /users/me. Send only the fields to change; omitted fields stay as they are."""

    # forbid: `{"email": ...}` or `{"status": ...}` is an error, never silently ignored.
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    bio: str | None = Field(default=None, max_length=500, description="null clears the bio")
    locale: Literal["en", "de", "es"] | None = None

    @field_validator("display_name", "locale")
    @classmethod
    def reject_null(cls, value: str | None) -> str | None:
        # Runs only for fields the client actually sent, so an explicit null is an error
        # for fields that cannot be empty (bio is the one field that may be cleared).
        if value is None:
            raise ValueError("must not be null")
        return value


class PublicUserResponse(ApiModel):
    """What anybody may see about a user. No email, no internal status."""

    id: UUID
    username: str
    display_name: str
    bio: str | None
    avatar_asset_id: UUID | None
    banner_asset_id: UUID | None
    created_at: datetime


class UserResponse(PublicUserResponse):
    """Full record for the owner and administrators."""

    email: str
    locale: str
    status: str
    updated_at: datetime
    version: int
