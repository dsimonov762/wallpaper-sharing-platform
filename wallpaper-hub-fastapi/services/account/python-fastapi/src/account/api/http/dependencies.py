"""Objects that routes receive through `Depends(...)`.

Dependencies can depend on each other: get_user_service needs a session and an identity
provider, FastAPI builds them first (once per request) and passes them in.
"""

import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from account.domain.exceptions import ServiceUnavailableException, UnauthorizedException
from account.domain.identity import IdentityProvider
from account.domain.user_service import UserService
from account.repository.user_repository import UserRepository
from account.security.current_user import CurrentUser
from account.security.errors import JwksUnavailableError, TokenRejectedError
from account.security.jwt_validator import TokenValidator
from account.util.pagination import MAX_PAGE_SIZE

logger = logging.getLogger(__name__)


def get_engine(request: Request) -> AsyncEngine:
    return request.app.state.engine


async def get_session(request: Request) -> AsyncGenerator[AsyncSession]:
    """One session per request. Closing it rolls back anything left uncommitted."""
    async with request.app.state.session_factory() as session:
        yield session


def get_identity_provider(request: Request) -> IdentityProvider:
    return request.app.state.identity_provider


EngineDep = Annotated[AsyncEngine, Depends(get_engine)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
IdentityDep = Annotated[IdentityProvider, Depends(get_identity_provider)]


def get_token_validator(request: Request) -> TokenValidator:
    return request.app.state.token_validator


TokenValidatorDep = Annotated[TokenValidator, Depends(get_token_validator)]

# Reads `Authorization: Bearer <token>`. auto_error=False: we raise our own problem+json
# error instead of FastAPI's default. Using this class also adds the "Authorize" button
# to the interactive docs at /docs.
bearer_scheme = HTTPBearer(auto_error=False)

_CHALLENGE = "Bearer"  # no credentials were sent (RFC 6750 section 3)
_CHALLENGE_INVALID = 'Bearer error="invalid_token"'  # credentials were sent but are bad


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    validator: TokenValidatorDep,
) -> CurrentUser:
    """Who is calling? Verify the Bearer token and describe the caller, or fail with 401/503."""
    if credentials is None:
        raise UnauthorizedException(
            "Authentication is required.", headers={"WWW-Authenticate": _CHALLENGE}
        )
    try:
        claims = await validator.validate(credentials.credentials)
    except TokenRejectedError as exc:
        # The precise reason goes to our log only; the client gets one generic message,
        # so an attacker learns nothing about which check failed.
        logger.info("Access token rejected: %s", exc.reason)
        raise UnauthorizedException(
            "The access token is invalid or has expired.",
            headers={"WWW-Authenticate": _CHALLENGE_INVALID},
        ) from exc
    except JwksUnavailableError as exc:
        logger.error("Cannot load signing keys from the identity provider", exc_info=exc)
        raise ServiceUnavailableException("Authentication is temporarily unavailable.") from exc
    return CurrentUser.from_claims(claims)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def get_user_service(session: SessionDep, identity: IdentityDep) -> UserService:
    return UserService(session, UserRepository(session), identity)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


class PageQuery:
    """?page=0&size=20&sort=createdAt,desc  (size is capped at 100)."""

    def __init__(
        self,
        page: Annotated[int, Query(ge=0)] = 0,
        size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
        sort: Annotated[str, Query(description="field,asc|desc")] = "createdAt,desc",
    ) -> None:
        self.page = page
        self.size = size
        self.sort = sort


PageQueryDep = Annotated[PageQuery, Depends()]
