# account-service (Python / FastAPI) cheat sheet

Concept -> where it lives. Add a row every time you implement something new.

| Concept | File |
|---|---|
| Entry point, app factory, startup/shutdown (lifespan) | `src/account/main.py` |
| Typed config, env vars, secrets, fail-fast validation | `src/account/config/settings.py` |
| Liveness + readiness endpoints | `src/account/api/http/health.py` |
| Dependency injection (`Depends`, `Annotated` aliases) | `src/account/api/http/dependencies.py` |
| DB engine/pool, session factory, reachability check | `src/account/repository/database.py` |
| Tables as Python classes (SQLAlchemy ORM) | `src/account/repository/models.py` |
| Schema versioning (Alembic), hand-written CHECK constraint | `migrations/`, `alembic.ini` |
| Request/response models, validation rules, camelCase JSON | `src/account/dto/` |
| Entity <-> DTO mapping (explicit, no accidental leaks) | `src/account/mapper/user_mapper.py` |
| Business rules, transaction boundary (commit) | `src/account/domain/user_service.py` |
| All SQL, sort whitelist, pagination query | `src/account/repository/user_repository.py` |
| Exceptions -> RFC 9457 problem+json (one handler); 401/403/412/428/503, extra response headers | `src/account/domain/exceptions.py`, `src/account/api/http/errors.py` |
| Identity provider port (create, delete, disable a login) + local stand-in | `src/account/domain/identity.py`, `src/account/infra/local_identity.py` |
| Routers (`/api/v1/...`), including `/users/me` | `src/account/api/http/registrations.py`, `users.py`, `router.py` |
| Paging/sorting helpers | `src/account/util/pagination.py` |
| Unit tests (no DB), faking a function with `monkeypatch` | `tests/unit/` |
| Integration tests (real Postgres, `-m integration`) | `tests/integration/` |
| Documented error responses in OpenAPI (401, 403, 412, 428 ...) | `src/account/api/http/responses.py` |
| JWT validation (RS256 allow-list, `iss`, `aud`, `exp`/`nbf` leeway, `typ`) | `src/account/security/jwt_validator.py` |
| Signing-key cache (JWKS): rotation, throttled reload, stale keys if Keycloak is down | `src/account/security/jwks.py` |
| Token errors: bad token (401) vs keys unavailable (503) | `src/account/security/errors.py` |
| The caller as an object (`CurrentUser`: id, email, roles, scope) | `src/account/security/current_user.py` |
| Auth dependency: `Authorization: Bearer` -> `CurrentUser`, 401/503 problem+json | `src/account/api/http/dependencies.py` (`get_current_user`) |
| Permission enum + role -> permission table (code checks permissions, not roles) | `src/account/security/permissions.py` |
| Protect an endpoint: `require_permission`, `require_role`, internal-only | `src/account/api/http/guards.py` |
| Default-deny router (every route needs a token unless it opts out) | `src/account/api/http/users.py` |
| Ownership check, done before the lookup (no id probing) | `src/account/security/authorization.py` |
| ETag / `If-Match` parsing (428 missing, 412 stale, `*`, weak tags) | `src/account/api/http/etag.py` |
| Optimistic locking: `version` column, `StaleDataError` -> 412 | `src/account/repository/models.py`, `src/account/domain/user_service.py` (`update_profile`) |
| Partial update with `PATCH` (only sent fields change, unknown fields rejected) | `src/account/dto/user.py` (`UpdateProfileRequest`), `src/account/mapper/user_mapper.py` (`to_profile_changes`) |
| Real Keycloak admin client (cached admin token, create/delete/disable user, assign role) | `src/account/infra/keycloak_identity.py` |
| Choose local or Keycloak provider from settings (fail-fast checks) | `src/account/infra/identity_factory.py`, `src/account/config/settings.py` |
| Compensating action: undo the Keycloak user when the DB step fails | `src/account/domain/user_service.py` (`register`, `_remove_identity`) |
| Keycloak realm: clients, roles, demo users, service-account admin roles | `infra/keycloak/realm-export.json` (repo root) |
| Refresh and logout through Keycloak's token endpoints (3.7) | _add the file path from the 3.7 delivery_ |
| Fake login for tests (own RSA key + fake JWKS, no Keycloak) | `tests/unit/security/conftest.py`, `tests/integration/conftest.py` (`auth_headers`) |
| Mocking Keycloak's HTTP API (`httpx2.MockTransport`) | `tests/unit/test_keycloak_identity.py` |
| Tests against the real Keycloak (skip if not running) | `tests/integration/test_keycloak_registration.py` |

## Commands

| Task | Command |
|---|---|
| Apply migrations | `just account-migrate` |
| New migration after changing `models.py` | `just account-migration "add avatar column"` |
| Unit tests | `uv run pytest` |
| Integration tests (infra must be up + migrated) | `just account-test-integration` |
| Register against real Keycloak instead of the local stand-in | in `.env`: `ACCOUNT_IDENTITY_PROVIDER=keycloak` and `ACCOUNT_KEYCLOAK_CLIENT_SECRET=dev-secret-account-svc` |
| Get a real token for `alice` (local testing only) | `curl.exe -s -X POST http://localhost:8180/realms/wallpaperhub/protocol/openid-connect/token -d client_id=dev-tools -d username=alice -d password=alice123 -d grant_type=password` |
| Apply a changed `realm-export.json` | recreate Keycloak's data (the `keycloak` database, or `just infra-reset`, which wipes all dev data), then `just infra-up` |
