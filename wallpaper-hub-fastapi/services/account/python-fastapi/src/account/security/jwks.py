"""A small async cache for Keycloak's public signing keys (the JWKS document).

Why a cache?  Every request carries a token, and checking its signature needs
the public key. Downloading the key set per request would be slow and would make
Keycloak a hard dependency of every call.

Rules implemented here:

* Keys are kept for ``ttl_seconds`` and then reloaded.
* A token with an unknown key id (``kid``) triggers one reload, because Keycloak
  may have rotated its keys.
* Reloads are throttled to one per ``min_refetch_seconds``. Without this, an
  attacker could send tokens with random ``kid`` values and make us hammer Keycloak.
* Concurrent requests share a single reload (a lock plus a re-check).
* If a reload fails but the key we need is still cached, we keep using it
  ("stale if error"): a short Keycloak outage should not log everyone out.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, cast

import httpx2
from jwt import PyJWK, PyJWKError

from account.security.errors import JwksUnavailableError, TokenRejectedError

JwksFetcher = Callable[[], Awaitable[Mapping[str, object]]]


def http_jwks_fetcher(client: httpx2.AsyncClient, url: str) -> JwksFetcher:
    """Build a fetcher that downloads the JWKS document over HTTP.

    The client is owned by the caller (created and closed in the app lifespan),
    and should have a short timeout, for example ``httpx2.AsyncClient(timeout=5.0)``.
    """

    async def fetch() -> Mapping[str, object]:
        try:
            response = await client.get(url)
            response.raise_for_status()
            document: object = response.json()
        except (httpx2.HTTPError, ValueError) as exc:
            raise JwksUnavailableError(f"cannot load JWKS from {url}") from exc
        if not isinstance(document, dict):
            raise JwksUnavailableError("JWKS document is not a JSON object")
        return cast(dict[str, object], document)

    return fetch


def _parse_signing_keys(document: Mapping[str, object], algorithms: set[str]) -> dict[str, PyJWK]:
    """Turn the JWKS JSON into ``{kid: key}``, keeping only usable signature keys."""
    raw_keys = document.get("keys")
    if not isinstance(raw_keys, list):
        raise JwksUnavailableError("JWKS document has no 'keys' list")

    keys: dict[str, PyJWK] = {}
    for item in cast(list[object], raw_keys):
        if not isinstance(item, dict):
            continue
        jwk = cast(dict[str, Any], item)
        kid = jwk.get("kid")
        if not isinstance(kid, str):
            continue
        # Keycloak also publishes encryption keys (use="enc"); they never sign tokens.
        if jwk.get("use", "sig") != "sig":
            continue
        alg = jwk.get("alg")
        if alg is not None and alg not in algorithms:
            continue
        try:
            keys[kid] = PyJWK.from_dict(jwk)
        except PyJWKError:
            continue
    return keys


class JwksCache:
    def __init__(
        self,
        fetcher: JwksFetcher,
        *,
        algorithms: tuple[str, ...] = ("RS256",),
        ttl_seconds: float = 600.0,
        min_refetch_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetcher = fetcher
        self._algorithms = set(algorithms)
        self._ttl = ttl_seconds
        self._min_refetch = min_refetch_seconds
        self._clock = clock
        self._keys: dict[str, PyJWK] = {}
        self._loaded_at: float | None = None  # last SUCCESSFUL load
        self._attempted_at: float | None = None  # last attempt, success or not
        self._lock = asyncio.Lock()

    async def get_key(self, kid: str) -> PyJWK:
        """Return the signing key for ``kid`` or raise.

        Raises ``TokenRejectedError("unknown_key")`` if the provider does not know it,
        ``JwksUnavailableError`` if we have no keys at all and cannot load them.
        """
        key = self._keys.get(kid)
        if key is not None and not self._expired():
            return key

        await self._refresh_if_allowed()

        key = self._keys.get(kid)
        if key is not None:
            return key
        if not self._keys:
            raise JwksUnavailableError("no signing keys available")
        raise TokenRejectedError("unknown_key")

    def _expired(self) -> bool:
        return self._loaded_at is None or self._clock() - self._loaded_at >= self._ttl

    def _throttled(self) -> bool:
        return (
            self._attempted_at is not None
            and self._clock() - self._attempted_at < self._min_refetch
        )

    async def _refresh_if_allowed(self) -> None:
        seen_attempt = self._attempted_at
        async with self._lock:
            # Another request may have reloaded while we waited for the lock.
            if self._attempted_at != seen_attempt or self._throttled():
                return
            self._attempted_at = self._clock()
            try:
                document = await self._fetcher()
                keys = _parse_signing_keys(document, self._algorithms)
            except JwksUnavailableError:
                if not self._keys:
                    raise
                return  # keep serving the stale keys
            self._keys = keys
            self._loaded_at = self._clock()
