"""/api/v1/auth: educational token endpoints (README sections 5.1 and 7).

Both endpoints are PUBLIC on purpose: they are used when the access token has already
expired, so the only credential available is the refresh token in the request body.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status

from account.api.http.responses import BAD_REQUEST
from account.dto.auth import RefreshTokenRequest, TokenResponse
from account.dto.problem import ProblemDetail
from account.infra.keycloak_tokens import KeycloakTokenClient
from account.mapper.token_mapper import to_token_response

router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_REFRESH_TOKEN: dict[int | str, dict[str, Any]] = {
    401: {"model": ProblemDetail, "description": "The refresh token is invalid or has expired"}
}


def get_token_client(request: Request) -> KeycloakTokenClient:
    return request.app.state.token_client


TokenClientDep = Annotated[KeycloakTokenClient, Depends(get_token_client)]


@router.post("/refresh", responses={**BAD_REQUEST, **INVALID_REFRESH_TOKEN})
async def refresh_tokens(
    body: RefreshTokenRequest, tokens: TokenClientDep, response: Response
) -> TokenResponse:
    """Exchange a refresh token for a new access token (and a new refresh token)."""
    result = await tokens.refresh(body.refresh_token)
    # RFC 6749 section 5.1: a response that carries tokens must never be cached.
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return to_token_response(result)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**BAD_REQUEST, **INVALID_REFRESH_TOKEN},
)
async def logout(body: RefreshTokenRequest, tokens: TokenClientDep) -> None:
    """End the session behind a refresh token (all of its tokens stop working)."""
    await tokens.logout(body.refresh_token)
