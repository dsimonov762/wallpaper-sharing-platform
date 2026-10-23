"""/api/v1/users.

Every route here needs a valid token: the router itself carries `get_current_user`, so a
route added later is protected by default and has to opt OUT on purpose. On top of that:
listing needs the `user:list` permission (ADMIN), deleting needs ownership or ADMIN, and
`/users/me` is the caller's own profile (read: `profile:read`, edit: `profile:write`).

`/me` is declared BEFORE `/{user_id}` on purpose: routes match in order, and otherwise
FastAPI would try to read the word "me" as a UUID.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status

from account.api.http.dependencies import (
    CurrentUserDep,
    PageQueryDep,
    UserServiceDep,
    get_current_user,
)
from account.api.http.etag import etag_for, parse_if_match
from account.api.http.guards import require_permission
from account.api.http.responses import (
    BAD_REQUEST,
    FORBIDDEN,
    NOT_FOUND,
    PRECONDITION_FAILED,
    PRECONDITION_REQUIRED,
    UNAUTHORIZED,
)
from account.domain.exceptions import NotFoundException
from account.dto.page import Page
from account.dto.user import PublicUserResponse, UpdateProfileRequest, UserResponse
from account.mapper.user_mapper import to_profile_changes, to_public_user, to_user
from account.security.authorization import ensure_owner_or_permission
from account.security.current_user import CurrentUser
from account.security.permissions import Permission
from account.util.pagination import total_pages

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(get_current_user)],
    responses=UNAUTHORIZED,
)

ProfileReader = Annotated[CurrentUser, Depends(require_permission(Permission.PROFILE_READ))]
ProfileWriter = Annotated[CurrentUser, Depends(require_permission(Permission.PROFILE_WRITE))]


def _own_id(caller: CurrentUser) -> UUID:
    """The caller's user id. A token whose `sub` is not a UUID has no profile row."""
    try:
        return UUID(caller.id)
    except ValueError as error:
        raise NotFoundException("No profile exists for this account.") from error


@router.get(
    "",
    dependencies=[Depends(require_permission(Permission.USER_LIST))],
    responses={**BAD_REQUEST, **FORBIDDEN},
)
async def list_users(service: UserServiceDep, paging: PageQueryDep) -> Page[UserResponse]:
    result = await service.list_users(paging.page, paging.size, paging.sort)
    return Page[UserResponse](
        items=[to_user(user) for user in result.items],
        page=paging.page,
        size=paging.size,
        total_items=result.total,
        total_pages=total_pages(result.total, paging.size),
    )


@router.get("/me", responses={**FORBIDDEN, **NOT_FOUND})
async def get_my_profile(
    caller: ProfileReader, service: UserServiceDep, response: Response
) -> UserResponse:
    """The caller's own profile. The `ETag` header is what `PATCH` must send as `If-Match`."""
    user = await service.get(_own_id(caller))
    response.headers["ETag"] = etag_for(user.version)
    return to_user(user)


@router.patch(
    "/me",
    responses={
        **BAD_REQUEST,
        **FORBIDDEN,
        **NOT_FOUND,
        **PRECONDITION_FAILED,
        **PRECONDITION_REQUIRED,
    },
)
async def update_my_profile(
    body: UpdateProfileRequest,
    caller: ProfileWriter,
    service: UserServiceDep,
    response: Response,
    if_match: Annotated[
        str | None, Header(description='ETag from a previous GET, e.g. "3" (or *)')
    ] = None,
) -> UserResponse:
    """Edit your own profile. Send only the fields to change."""
    expected_versions = parse_if_match(if_match)
    user = await service.update_profile(
        _own_id(caller), to_profile_changes(body), expected_versions
    )
    response.headers["ETag"] = etag_for(user.version)
    return to_user(user)


@router.get("/{user_id}", responses={**BAD_REQUEST, **NOT_FOUND})
async def get_user(user_id: UUID, service: UserServiceDep) -> PublicUserResponse:
    return to_public_user(await service.get(user_id))


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**BAD_REQUEST, **FORBIDDEN, **NOT_FOUND},
)
async def delete_user(user_id: UUID, caller: CurrentUserDep, service: UserServiceDep) -> None:
    # Ownership is checked BEFORE the lookup: a stranger gets 403 whether or not the id
    # exists, so this endpoint cannot be used to find out which user ids are real.
    ensure_owner_or_permission(caller, user_id, Permission.USER_DELETE)
    await service.delete(user_id)
