"""Request and response models for /auth/refresh and /auth/logout."""

from pydantic import Field, SecretStr

from account.dto.base import ApiModel


class RefreshTokenRequest(ApiModel):
    # SecretStr: never printed in logs, repr() or error output.
    refresh_token: SecretStr = Field(min_length=1, max_length=8192)


class TokenResponse(ApiModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int = Field(description="Seconds until the access token expires")
    refresh_expires_in: int = Field(description="Seconds until the refresh token expires")
