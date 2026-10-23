"""POST /api/v1/registrations (public)."""

from fastapi import APIRouter, Response, status

from account.api.http.dependencies import UserServiceDep
from account.api.http.responses import BAD_REQUEST, CONFLICT
from account.dto.user import RegistrationRequest, UserResponse
from account.mapper.user_mapper import to_registration, to_user

router = APIRouter(prefix="/registrations", tags=["registrations"])


@router.post("", status_code=status.HTTP_201_CREATED, responses={**BAD_REQUEST, **CONFLICT})
async def register(
    request: RegistrationRequest, service: UserServiceDep, response: Response
) -> UserResponse:
    user = await service.register(to_registration(request))
    response.headers["Location"] = f"/api/v1/users/{user.id}"
    return to_user(user)
