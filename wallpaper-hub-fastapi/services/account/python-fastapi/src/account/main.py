"""Application entry point: builds the FastAPI app.

Bootstrap order (README section 12). Done so far: config -> database pool -> users API
-> token validation -> identity provider.
Still to come: logging+telemetry -> DI wiring -> HTTP/gRPC/management
-> consumers/workers/schedulers -> graceful shutdown.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx2
from fastapi import FastAPI

from account.api.http.errors import register_exception_handlers
from account.api.http.health import router as health_router
from account.api.http.router import api_router
from account.config.settings import get_settings
from account.infra.identity_factory import create_identity_provider
from account.infra.keycloak_tokens import KeycloakTokenClient
from account.repository.database import create_engine, create_session_factory
from account.security.jwks import JwksCache, http_jwks_fetcher
from account.security.jwt_validator import TokenValidator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()  # fail fast: invalid configuration stops startup here
    engine = create_engine(settings)  # lazy: the service starts even if the DB is down
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    # One HTTP client for everything we ask Keycloak (signing keys, admin API). Nothing is
    # requested here: keys and admin tokens are fetched on first use, so the service also
    # starts when Keycloak is down.
    http_client = httpx2.AsyncClient(timeout=settings.keycloak_timeout_s)
    app.state.identity_provider = create_identity_provider(settings, http_client)
    app.state.token_client = KeycloakTokenClient(
        http_client,
        base_url=settings.keycloak_base_url,
        realm=settings.keycloak_realm,
        issuer=settings.oidc_issuer,
    )
    jwks = JwksCache(
        http_jwks_fetcher(http_client, settings.jwks_url),
        ttl_seconds=settings.oidc_jwks_ttl_seconds,
        min_refetch_seconds=settings.oidc_jwks_min_refetch_seconds,
    )
    app.state.token_validator = TokenValidator(
        jwks,
        issuer=settings.oidc_issuer,
        audience=settings.oidc_audience,
        leeway_seconds=settings.oidc_leeway_seconds,
    )
    try:
        yield
    finally:
        await http_client.aclose()  # close the connection pool used for Keycloak calls
        await engine.dispose()  # close pooled connections on shutdown


def create_app() -> FastAPI:
    app = FastAPI(title="Wallpaper Hub - account-service", version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(api_router)
    return app


app = create_app()
