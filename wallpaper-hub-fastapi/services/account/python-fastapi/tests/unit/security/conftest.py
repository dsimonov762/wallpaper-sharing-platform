"""Shared fixtures for authorization tests: a fake Keycloak (own RSA key + fake JWKS)
and a FastAPI app that already trusts it. Tests add their own routes to `auth_app`."""

import asyncio
import json
import time
from collections.abc import Callable, Mapping
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from jwt.algorithms import RSAAlgorithm

from account.api.http.errors import register_exception_handlers
from account.security.jwks import JwksCache
from account.security.jwt_validator import TokenValidator

ISSUER = "http://localhost:8180/realms/wallpaperhub"
AUDIENCE = "account-svc"
KID = "test-key"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


async def _fake_jwks() -> Mapping[str, object]:
    await asyncio.sleep(0)
    jwk = json.loads(RSAAlgorithm.to_jwk(_private_key.public_key()))
    jwk.update({"kid": KID, "use": "sig", "alg": "RS256"})
    return {"keys": [jwk]}


MakeToken = Callable[..., dict[str, str]]


@pytest.fixture
def auth_headers() -> MakeToken:
    """``auth_headers("USER", sub="u-1")`` -> an Authorization header with a valid token."""

    def make(*roles: str, sub: str = "user-1", **claims: Any) -> dict[str, str]:
        payload: dict[str, Any] = {
            "sub": sub,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "typ": "Bearer",
            "exp": int(time.time()) + 300,
            "realm_access": {"roles": list(roles)},
            **claims,
        }
        token = jwt.encode(payload, _private_key, algorithm="RS256", headers={"kid": KID})
        return {"Authorization": f"Bearer {token}"}

    return make


@pytest.fixture
def auth_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.state.token_validator = TokenValidator(
        JwksCache(_fake_jwks), issuer=ISSUER, audience=AUDIENCE
    )
    return app
