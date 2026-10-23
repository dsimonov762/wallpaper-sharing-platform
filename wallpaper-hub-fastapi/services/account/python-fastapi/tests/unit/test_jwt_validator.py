"""Unit tests for JWT validation. No network and no Keycloak: we create our own
RSA keys and serve them through a fake JWKS fetcher."""

import asyncio
import json
import time
from collections.abc import Mapping
from typing import Any, cast

import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from account.security.errors import JwksUnavailableError, TokenRejectedError
from account.security.jwks import JwksCache, http_jwks_fetcher
from account.security.jwt_validator import TokenValidator

ISSUER = "http://localhost:8180/realms/wallpaperhub"
AUDIENCE = "account-svc"

pytestmark = pytest.mark.asyncio


class Signer:
    """One RSA key pair plus helpers to publish it as JWKS and sign tokens."""

    def __init__(self, kid: str) -> None:
        self.kid = kid
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def jwk(self, **extra: str) -> dict[str, Any]:
        document = json.loads(RSAAlgorithm.to_jwk(self.private_key.public_key()))
        document.update({"kid": self.kid, "use": "sig", "alg": "RS256", **extra})
        return document

    def token(self, headers: dict[str, Any] | None = None, **overrides: Any) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "sub": "user-1",
            "iss": ISSUER,
            "aud": AUDIENCE,
            "typ": "Bearer",
            "iat": now,
            "exp": now + 300,
            **overrides,
        }
        claims = {name: value for name, value in claims.items() if value is not None}
        return jwt.encode(
            claims,
            self.private_key,
            algorithm="RS256",
            headers={"kid": self.kid, **(headers or {})},
        )


class FakeJwks:
    """Stands in for Keycloak's certs endpoint and counts the calls."""

    def __init__(self, *signers: Signer) -> None:
        self.keys: list[dict[str, Any]] = [signer.jwk() for signer in signers]
        self.calls = 0
        self.fail = False

    async def __call__(self) -> Mapping[str, object]:
        self.calls += 1
        await asyncio.sleep(0)  # let other tasks run, like a real network call
        if self.fail:
            raise JwksUnavailableError("down")
        return {"keys": self.keys}


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def signer() -> Signer:
    return Signer("key-1")


@pytest.fixture
def jwks(signer: Signer) -> FakeJwks:
    return FakeJwks(signer)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def validator(jwks: FakeJwks, clock: FakeClock) -> TokenValidator:
    cache = JwksCache(jwks, ttl_seconds=600, min_refetch_seconds=30, clock=clock)
    return TokenValidator(cache, issuer=ISSUER, audience=AUDIENCE, leeway_seconds=30)


async def reason_of(validator: TokenValidator, token: str) -> str:
    with pytest.raises(TokenRejectedError) as info:
        await validator.validate(token)
    return info.value.reason


# --- happy path and the claim checks -------------------------------------------------


async def test_valid_token_returns_claims(validator: TokenValidator, signer: Signer) -> None:
    claims = await validator.validate(signer.token(email="a@example.com"))
    assert claims["sub"] == "user-1"
    assert claims["email"] == "a@example.com"


async def test_audience_list_containing_service_is_accepted(
    validator: TokenValidator, signer: Signer
) -> None:
    claims = await validator.validate(signer.token(aud=["account", AUDIENCE]))
    assert claims["sub"] == "user-1"


async def test_expired_token_is_rejected(validator: TokenValidator, signer: Signer) -> None:
    token = signer.token(exp=int(time.time()) - 120)
    assert await reason_of(validator, token) == "expired"


async def test_leeway_forgives_small_clock_skew(validator: TokenValidator, signer: Signer) -> None:
    await validator.validate(signer.token(exp=int(time.time()) - 10))
    await validator.validate(signer.token(nbf=int(time.time()) + 10))


async def test_not_yet_valid_token_is_rejected(validator: TokenValidator, signer: Signer) -> None:
    token = signer.token(nbf=int(time.time()) + 120)
    assert await reason_of(validator, token) == "not_yet_valid"


async def test_wrong_issuer_is_rejected(validator: TokenValidator, signer: Signer) -> None:
    assert await reason_of(validator, signer.token(iss="http://evil.example/realm")) == "bad_issuer"


async def test_wrong_audience_is_rejected(validator: TokenValidator, signer: Signer) -> None:
    assert await reason_of(validator, signer.token(aud="media-svc")) == "bad_audience"


@pytest.mark.parametrize("typ", ["Refresh", "ID", None])
async def test_only_bearer_tokens_are_accepted(
    validator: TokenValidator, signer: Signer, typ: str | None
) -> None:
    assert await reason_of(validator, signer.token(typ=typ)) == "bad_type"


@pytest.mark.parametrize("claim", ["exp", "sub"])
async def test_missing_required_claim_is_rejected(
    validator: TokenValidator, signer: Signer, claim: str
) -> None:
    assert await reason_of(validator, signer.token(**{claim: None})) == "missing_claim"


# --- signature and header attacks ------------------------------------------------------


async def test_token_signed_by_another_key_is_rejected(validator: TokenValidator) -> None:
    impostor = Signer("key-1")  # same kid, different key pair
    assert await reason_of(validator, impostor.token()) == "bad_signature"


async def test_alg_none_is_rejected(validator: TokenValidator) -> None:
    now = int(time.time())
    claims = {"sub": "x", "iss": ISSUER, "aud": AUDIENCE, "typ": "Bearer", "exp": now + 300}
    token = jwt.encode(claims, "", algorithm="none", headers={"kid": "key-1"})
    assert await reason_of(validator, token) == "bad_algorithm"


async def test_hs256_token_is_rejected(validator: TokenValidator) -> None:
    now = int(time.time())
    claims = {"sub": "x", "iss": ISSUER, "aud": AUDIENCE, "typ": "Bearer", "exp": now + 300}
    token = jwt.encode(claims, "a-shared-secret-of-32-bytes-long!", "HS256", {"kid": "key-1"})
    assert await reason_of(validator, token) == "bad_algorithm"


async def test_garbage_is_rejected(validator: TokenValidator) -> None:
    assert await reason_of(validator, "not-a-jwt") == "malformed"


async def test_token_without_kid_is_rejected(validator: TokenValidator, signer: Signer) -> None:
    token = jwt.encode(
        {"sub": "x", "iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) + 60},
        signer.private_key,
        algorithm="RS256",
    )
    assert await reason_of(validator, token) == "missing_kid"


# --- key cache behaviour -------------------------------------------------------------------


async def test_keys_are_fetched_once_and_cached(
    validator: TokenValidator, signer: Signer, jwks: FakeJwks
) -> None:
    for _ in range(5):
        await validator.validate(signer.token())
    assert jwks.calls == 1


async def test_key_rotation_triggers_one_refetch(
    validator: TokenValidator, signer: Signer, jwks: FakeJwks, clock: FakeClock
) -> None:
    await validator.validate(signer.token())
    rotated = Signer("key-2")
    jwks.keys = [signer.jwk(), rotated.jwk()]
    clock.now += 31  # past the throttle window
    await validator.validate(rotated.token())
    assert jwks.calls == 2


async def test_unknown_key_ids_cannot_flood_the_provider(
    validator: TokenValidator, signer: Signer, jwks: FakeJwks
) -> None:
    await validator.validate(signer.token())
    for number in range(20):
        stranger = Signer(f"random-{number}")
        assert await reason_of(validator, stranger.token()) == "unknown_key"
    assert jwks.calls <= 2  # first load plus at most one throttled retry


async def test_keys_are_reloaded_after_ttl(
    validator: TokenValidator, signer: Signer, jwks: FakeJwks, clock: FakeClock
) -> None:
    await validator.validate(signer.token())
    clock.now += 601
    await validator.validate(signer.token())
    assert jwks.calls == 2


async def test_concurrent_cold_start_loads_keys_once(
    validator: TokenValidator, signer: Signer, jwks: FakeJwks
) -> None:
    results = await asyncio.gather(*(validator.validate(signer.token()) for _ in range(10)))
    assert len(results) == 10
    assert jwks.calls == 1


async def test_provider_down_at_start_means_unavailable(
    validator: TokenValidator, signer: Signer, jwks: FakeJwks
) -> None:
    jwks.fail = True
    with pytest.raises(JwksUnavailableError):
        await validator.validate(signer.token())


async def test_stale_keys_are_used_when_provider_goes_down(
    validator: TokenValidator, signer: Signer, jwks: FakeJwks, clock: FakeClock
) -> None:
    await validator.validate(signer.token())
    jwks.fail = True
    clock.now += 601
    claims = await validator.validate(signer.token())
    assert claims["sub"] == "user-1"


async def test_encryption_keys_in_jwks_are_ignored(clock: FakeClock) -> None:
    signing, encryption = Signer("sig-key"), Signer("enc-key")
    jwks = FakeJwks(signing)
    jwks.keys.append(encryption.jwk(use="enc", alg="RSA-OAEP"))
    validator = TokenValidator(JwksCache(jwks, clock=clock), issuer=ISSUER, audience=AUDIENCE)
    await validator.validate(signing.token())
    assert await reason_of(validator, encryption.token()) == "unknown_key"


# --- the real HTTP fetcher (with a fake transport, still no network) -------------------------


async def test_http_fetcher_returns_the_document(signer: Signer) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert str(request.url) == "http://kc/certs"
        return httpx2.Response(200, json={"keys": [signer.jwk()]})

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as client:
        document = await http_jwks_fetcher(client, "http://kc/certs")()
    keys = cast(list[object], document["keys"])
    assert len(keys) == 1


@pytest.mark.parametrize(
    "response",
    [
        httpx2.Response(500),
        httpx2.Response(200, text="<html>not json</html>"),
        httpx2.Response(200, json=["not", "an", "object"]),
    ],
)
async def test_http_fetcher_maps_bad_answers_to_unavailable(response: httpx2.Response) -> None:
    transport = httpx2.MockTransport(lambda _request: response)
    async with httpx2.AsyncClient(transport=transport) as client:
        with pytest.raises(JwksUnavailableError):
            await http_jwks_fetcher(client, "http://kc/certs")()


async def test_http_fetcher_maps_connection_errors_to_unavailable() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("boom", request=request)

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as client:
        with pytest.raises(JwksUnavailableError):
            await http_jwks_fetcher(client, "http://kc/certs")()
