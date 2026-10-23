# Wallpaper Hub (Python / FastAPI) - Project Plan and Handoff

Prepared 16 Oct 2026 · updated 23 Oct 2026 (account through step 3.7 and Slice 4 step 4.1; media through slice M1; catalog through slice C1; notification through slice N1) · Python 3.14.5 · FastAPI · uv · Ruff · Pyright/Pylance · Windows 11 + Docker Desktop (WSL2)

## 1. Project at a glance

- **What:** Wallpaper Hub is a polyglot microservice reference design (README.md): four services (account, media, catalog, notification) plus an API gateway, built contract-first. We implement it in Python (FastAPI).
- **Goal:** practical knowledge plus a reusable template for future projects, built as close as possible to real production setups for small and medium organizations.
- **Learner:** basic Python, zero knowledge of FastAPI and the Python ecosystem. Explain every new concept simply and explain new code line by line.
- **Order of work (README §17):** finish Phase 1 (account-service, the template) completely, then media, catalog, notification, gateway, e2e. The user has temporarily left this order three times (media on 22 Oct, catalog on 23 Oct, notification on 23 Oct); on 23 Oct he also jumped inside Phase 1 from step 3.7 to Slice 4 (step 3.8 stays open). Phase 1 resumes afterwards.
- **Stack:** Python 3.14.5, FastAPI, Pydantic v2, SQLAlchemy 2 (async) + asyncpg, Alembic, PyMongo async API (catalog), redis-py async API (notification), pytest + pytest-asyncio, Ruff (lint + format), Pyright strict (Pylance in VS Code), uv, just, Docker Compose.

| Item | Value |
| --- | --- |
| OS / shell | Windows 11, PowerShell. Docker Desktop with the WSL2 engine only (no other Linux distro) |
| Editor | VS Code with Python, Pylance, Ruff, Docker, Even Better TOML |
| Tools (winget) | Git, uv (installs Python itself), just, VS Code |
| Repo | `C:\dev\wallpaper-hub` |
| Throwaway practice app | `C:\dev\fastapi-playground` (notes API, Phase -1, finished) |

## 2. Working agreement

- One slice at a time. Each slice arrives as an overlay zip (`account-sliceN-*.zip`, `catalog-sliceCN-*.zip`, `notification-sliceN<k>-*.zip`) extracted over the repo root. It replaces files inside that service's folder only (`services/<service>/python-fastapi/`). `justfile` and `infra/docker-compose.yml` are never overwritten: new just recipes, compose blocks and `infra/.env` lines are pasted in by hand from a separate `...-paste-in.md` file (or, when it is only a few recipes, from the reply itself). One deliberate exception: the shared `contracts/i18n/{en,de,es}.json` files are included in the account i18n zip (they are the shared message bundles, not user-owned config).
- Claude verifies in its sandbox: Ruff, Pyright strict, pytest, live HTTP smoke test, Alembic up/down, using a natively installed Postgres (and, since 3.6, a natively installed Keycloak 26.7.0 running the project's realm file). Since catalog C1 the sandbox also runs a native **MongoDB 8.3.7**, installed from conda-forge with micromamba (`conda.anaconda.org` is reachable from the sandbox; apt has no MongoDB package). It can also run a second `mongod --auth` to test the real credential URI form. Since notification N1 it also runs a native **Redis 8.8.3** (the same version as the compose image), compiled from the source tag via `codeload.github.com` with `make` (several minutes on one CPU core; apt only offers Redis 7.0). **The sandbox has no Docker**, so compose, Dockerfiles, Kafka, Elasticsearch (to be probed at C3) and the user's exact Keycloak setup stay unverified until the user runs them. Every slice ends with an honest 'verified vs not verified' list.
- When the repo is not in the sandbox (only the files the user pasted), Claude builds a reduced mirror of just those files (plus a stub for anything missing, such as `dto/base.py`) and verifies the new code there. Account step 4.1 was verified this way; the 'not verified' list then says so (section 9).
- Sandbox tips: Python 3.14.x comes from `uv python install 3.14` (the sandbox had 3.14.4 while the user has 3.14.5; the system Python in the sandbox is 3.12, enough for a reduced mirror); the tool shell is `sh`, so no brace expansion (use one `mkdir -p` per folder); start long builds and servers with `setsid nohup ... &` (plain background jobs are killed when the tool call ends); use a bracket pattern such as `pkill -f "uvicorn notificatio[n]"` so the command does not kill its own shell.
- The user runs `just account-sync`, `account-migrate`, `account-check`, `account-test-integration`, `account-run` (and the `media-*`, `catalog-*` and `notification-*` equivalents) and reports results or pastes errors.
- Style: plain language, why before how, line-by-line for new code, exercises at the end, README fidelity, mention trade-offs, build nothing beyond the current slice.
- `uv.lock` is the source of truth for versions. Search the web before pinning image tags or fast-moving libraries.

## 3. Design cheat summary (README map)

| Service | Stores | Role |
| --- | --- | --- |
| account | Postgres (users, outbox\_event, audit\_log), Redis cache | registration, profiles, outbox, Kafka producer, gRPC server |
| media | Postgres, S3/MinIO, Redis queue | uploads, image pipeline |
| catalog | MongoDB, Elasticsearch, Redis | wallpapers, search, GraphQL, gRPC client |
| notification | Redis as primary DB | event emails, SSE/WebSocket inbox, digest |
| gateway | none | routing, token validation, rate limit, aggregated docs |
| Keycloak | own Postgres DB | OIDC, roles USER/MODERATOR/ADMIN, service accounts |

Ports per service: HTTP 8080, management 8081, gRPC 9090 (account only). Dev host ports: Keycloak 8180, Mailpit UI 8025 / SMTP 1025, Postgres 5432, Redis 6379, MongoDB 27017. Local `uvicorn` ports (each service runs on its own so they can run side by side): account 8080, catalog 8082, notification 8083, media 8090.

| Need | README section |
| --- | --- |
| Principles, architecture, services | 1, 2, 3 |
| End-to-end flow, avatar denormalization, outbox, SSE | 4.1 - 4.4 |
| REST endpoints; paging, errors, idempotency, ETag, i18n | 5.1, 5.2 |
| Exception model, gRPC, GraphQL, Kafka/Avro | 5.3 - 5.6 |
| Tables, collections, Redis keys | 6 (catalog: 6.3 MongoDB, 6.4 Elasticsearch, 6.5 Redis; notification: 6.5 Redis keys) |
| Security (Keycloak, JWT, roles) | 7 |
| Resilience, background jobs | 8, 9 |
| Media pipeline | 10 |
| Observability, audit | 11 |
| Service layout template, repo layout, testing | 12, 13, 14 |
| Roadmap, decision log | 17, 18 |

## 4. Current state (update this section as you go)

**Where we stopped:** account Slice 3 steps 3.1 - 3.7 are delivered and green (after 3.6: 162 unit + 70 integration tests). Step 3.8 is deliberately **deferred**: revisit after media slice M2, because M2 copies the fake-JWT test helpers once more (catalog C2 will copy them a third time and notification N2 a fourth time, so decide on 3.8 before or right after C2). On 22 Oct 2026 the user temporarily moved to **Phase 2 (media-service)**: slice **M1 is delivered and green** (22 unit + 10 integration tests); next media step is **M2**. On 23 Oct 2026 the user temporarily moved to **Phase 3 (catalog-service)**: slice **C1 is delivered and confirmed green by the user** (in the sandbox: 67 unit + 16 integration tests against real MongoDB); next catalog step is **C2**. Later on 23 Oct 2026 the user temporarily moved to **Phase 4 (notification-service)**: slice **N1 is delivered and confirmed green by the user** (in the sandbox: 39 unit + 4 integration tests against a real Redis 8.8.3); next notification step is **N2**. Then, still on 23 Oct 2026, the user came back to **account Phase 1 and moved on to Slice 4** (cross-cutting API behavior) while 3.8 stays open: step **4.1 (i18n) is delivered and confirmed green by the user** (`account-slice4-i18n.zip`; in the sandbox: 27 new unit tests). **Next step: account 4.2** (correlation id and logging; the agreed design and the files it needs are in section 6). The user will convert the remaining hard-coded English exception `detail` messages to i18n keys himself, later (section 9). Steps 4.2 - 4.5 and Slices 5+ of account are untouched.

| Slice | What | Status |
| --- | --- | --- |
| -1 | Practice FastAPI notes app, exercises | ✅ done |
| 0 | Repo scaffold: contracts, infra compose, Keycloak realm, account skeleton, justfile | ✅ done, user confirmed |
| 1 | DB engine, Alembic migration 0001, /health/ready | ✅ done, user confirmed (8 unit + 3 integration) |
| 2 | Users API: registration, list, get, soft delete, problem+json errors, migration 0002 | ✅ done, user confirmed (34 unit + 14 integration) |
| 3 | Authentication and authorization: JWT validation, `CurrentUser`, permissions, protected routes, `/users/me` with ETag, Keycloak admin client, refresh/logout | 🟨 steps 3.1 - 3.7 done and confirmed, 3.8 open |
| 4 | Cross-cutting API behavior: i18n, correlation id and logging, Redis rate limit, idempotency, CORS and security headers | 🟨 4.1 done and confirmed (i18n), 4.2 - 4.5 open |
| 5 - 12 | see section 6 | ⬜ not started |
| M1 (media) | Skeleton, `media_asset`/`media_variant`, migration 0001, health | ✅ done, user confirmed (22 unit + 10 integration) |
| M2 - M7 (media) | see section 6, Phase 2 | ⬜ not started |
| C1 (catalog) | Skeleton, Mongo `wallpapers`, create/get/list/patch with ETag, indexes command, health | ✅ done, user confirmed all green (sandbox: 67 unit + 16 integration) |
| C2 - C7 (catalog) | see section 6, Phase 3 | ⬜ not started |
| N1 (notification) | Skeleton, Redis connection, health, problem+json errors | ✅ done, user confirmed all green (sandbox: 39 unit + 4 integration) |
| N2 - N7 (notification) | see section 6, Phase 4 | ⬜ not started |

**Infra (dev-only, from `infra/docker-compose.yml`, profile `infra`, started with `just infra-up`):**

- Images: `postgres:18.6-trixie`, `redis:8.8.3-trixie`, `axllent/mailpit:v1.31.2` (user's locally available tags), `quay.io/keycloak/keycloak:26.7.0` (`start-dev --import-realm`), `mongo:8.0` (added in C1; floating minor tag, replace with a pinned local tag if preferred).
- Postgres 18 needs the data volume mounted at `/var/lib/postgresql` (NOT `/var/lib/postgresql/data`). Claude told the user to fix this; confirm it was applied (check: `just infra-down` then `just infra-up` keeps the `users` table).
- One Postgres server, databases `account`, `media`, `keycloak` with roles `account_svc`, `media_svc`, `keycloak_svc`. Passwords live in `infra/.env` (git-ignored; template `infra/.env.example`). The init script runs only on an empty volume; `just infra-reset` wipes all data.
- **MongoDB (C1):** container `mongo` with root user `root` (`MONGO_ROOT_PASSWORD`) and volume `mongo-data`. `infra/mongo/init/01-create-catalog-user.js` runs once on an empty volume and creates user `catalog_svc` (password `CATALOG_DB_PASSWORD`, both in `infra/.env`) with `readWrite` on databases `catalog` and `catalog_test`. The user is created in database `catalog`, so the connection string needs `authSource=catalog`. To re-run the init script, remove only the Mongo volume (`docker volume rm <project>_mongo-data`), never `just infra-reset`.
- **Redis (N1):** the existing `redis` container is used as is; N1 needed no compose or `infra/.env` changes, and the user's integration tests passed against it. The notification service reads `NOTIFICATION_REDIS_URL` from its own `.env`. If the compose Redis ever gets a password, put it in the URL: `redis://:<password>@localhost:6379/0`. Notification keeps its data in logical database 0.
- Service config file: `services/account/python-fastapi/.env` containing `ACCOUNT_DATABASE_URL=postgresql+asyncpg://account_svc:<ACCOUNT_DB_PASSWORD>@localhost:5432/account`. To use real Keycloak for registration also set `ACCOUNT_IDENTITY_PROVIDER=keycloak` and `ACCOUNT_KEYCLOAK_CLIENT_SECRET=dev-secret-account-svc` (default provider is `local`; other `ACCOUNT_KEYCLOAK_*` and `ACCOUNT_OIDC_*` settings have working defaults). Optional since 4.1: `ACCOUNT_I18N_DIR` (folder with `en.json`, `de.json`, `es.json`); by default the service finds `contracts/i18n` by walking up from its own source folder.
- Keycloak realm `wallpaperhub`: admin console user `admin` (password `KEYCLOAK_ADMIN_PASSWORD` in `infra/.env`). Clients: `web-spa` (public, PKCE, redirect `http://localhost:3000/*`), `dev-tools` (public, password grant, LOCAL ONLY), `account-svc`, `media-svc`, `catalog-svc`, `notification-svc` (confidential, secret `dev-secret-<clientId>`, service accounts with role `internal`). Audience mapper adds `aud` for the four services. Demo users: `alice/alice123` (USER), `mod/mod123` (USER, MODERATOR), `admin-demo/admin123` (all three roles). The optional `gateway` client from README §7 does not exist yet.
- Token for testing: `curl.exe -s -X POST http://localhost:8180/realms/wallpaperhub/protocol/openid-connect/token -d client_id=dev-tools -d username=alice -d password=alice123 -d grant_type=password`
- Realm file changes made in step 3.6 (`infra/keycloak/realm-export.json`): the `account-svc` service account also holds the `realm-management` client roles `manage-users` and `view-realm` (the admin API returned 403 without them), and the realm's user profile makes `firstName`/`lastName` optional (otherwise a user created without names cannot log in: "Account is not fully set up"). Keycloak imports a realm only on its first start: after editing the file, recreate Keycloak's data (the `keycloak` database, or `just infra-reset`, which wipes all dev data).
- Observed in 3.6: tokens that service accounts get via client credentials carry no `aud` claim (only `web-spa` and `dev-tools` have the audience mappers). Not a problem yet; see section 9.

**account i18n (Slice 4, step 4.1, delivered 23 Oct 2026, confirmed green by the user):** every error response from the account service is localized from the `Accept-Language` header (en, de, es; default en).

- Files: `src/account/i18n/negotiation.py` (`resolve_locale(header)`: weights `q`, primary language only so `de-AT` gives `de`, `q=0` ignored, bad weight ignored, `*` and no match give `en`), `i18n/messages.py` (`MessageBundles`, `get_bundles()` loaded once, `translate(key, locale, **args)`, `find_bundle_dir()`), `i18n/__init__.py` (exports). Edited: `api/http/errors.py` (all four handlers localize; `request_locale(request)`; `Content-Language` response header), `domain/exceptions.py` (`title_key` on every class, optional `message_key` / `message_args` on `AppException`, optional `message_key` / `message_args` on `FieldIssue`; existing calls unchanged). Tests: `tests/unit/test_i18n.py` (27 tests).
- Bundles: `contracts/i18n/{en,de,es}.json`, flat dotted keys, 29 keys each (`error.<name>.title` / `.detail`, `validation.*`, `email.welcome.subject`), `{placeholders}`. Lookup order: requested language, then English, then the key itself (a warning is logged). A placeholder without a value stays visible as `{name}`. Tests enforce identical key sets and identical placeholder names in all three files.
- Behavior: titles, the validation `detail` and `errors[].message` are translated; `errors[].code` never changes with the language. Pydantic error types (required, too short/long, pattern, literal, range, int/uuid parsing, malformed JSON, email) map to `validation.*` keys. Framework 404 and 405 are localized (a route's own custom message is left as written). A 500 stays generic and localized. The locale is read straight from the request header inside the handlers, not from a middleware, so the unexpected-error handler also works; the locale middleware in the final order (step 4.5) is therefore optional.
- Fail fast: `register_exception_handlers(app)` loads the bundles immediately, so a missing `contracts/i18n` stops startup. `ACCOUNT_I18N_DIR` overrides the folder (read from `os.environ`, not from `Settings`; the Dockerfile in 11.1 must bundle the files and set it).
- Not done on purpose: the English `detail` strings written elsewhere in domain and security code (the user converts them himself later), messages of custom pydantic validators other than email (they keep pydantic's English text), the `Vary: Accept-Language` header.

**media-service (Phase 2, started 22 Oct 2026):** lives in `services/media/python-fastapi/`, same layout and conventions as account (section 5), env prefix `MEDIA_`, dev HTTP port **8090** (account uses 8080), database `media` with role `media_svc` (password in `infra/.env`; `.env` next to its `pyproject.toml` holds `MEDIA_DATABASE_URL=postgresql+asyncpg://media_svc:<password>@localhost:5432/media`). Delivered in M1: `main.py` (lazy engine, session factory), `config/settings.py`, `repository/{database,models}.py`, `domain/{models,exceptions}.py` (`MediaPurpose`, `MediaStatus`, `AppException` family), `api/http/{errors,health,dependencies,router}.py`, Alembic migration 0001. Ids are UUID v7 (`uuid.uuid7()`, new in Python 3.14). `media_variant.kind` has no CHECK yet (M5 adds it). `httpx2` is a dev dependency only until M2. Recipes: `media-sync | media-run | media-fix | media-check | media-migrate | media-migration 'message' | media-test-integration`. Not yet built in media: security, upload, S3/MinIO, queue, worker, events, i18n, correlation id, rate limiting, resilience wrappers.

**catalog-service (Phase 3, started 23 Oct 2026):** lives in `services/catalog/python-fastapi/`, same layered layout as account (section 5), env prefix `CATALOG_`, dev HTTP port **8082**, MongoDB database `catalog` (tests use `catalog_test`), role `catalog_svc`. Python is pinned to **3.14.5** here (`requires-python >=3.14.5`, `.python-version`), see section 9. The service ships its own `pyproject.toml` and `uv.lock` (new service, so unlike account's overlays it includes them).

- `.env` next to its `pyproject.toml` (template `.env.example`): `CATALOG_MONGODB_URI=mongodb://catalog_svc:<CATALOG_DB_PASSWORD>@localhost:27017/catalog?authSource=catalog`. Optional: `CATALOG_MONGODB_DATABASE`, `CATALOG_ENVIRONMENT`.
- Delivered in C1: `main.py` (app factory `create_app(settings)` + lifespan: lazy `AsyncMongoClient`, store and author directory on `app.state`), `config/settings.py` (`mongodb_uri` required `SecretStr`, `author_directory=local` refused when `environment=prod`), `domain/{models,exceptions,ports,wallpaper_service}.py`, `dto/{base,page,problem,wallpaper}.py`, `mapper/wallpaper_mapper.py`, `repository/{database,documents,wallpaper_repository,indexes}.py`, `infra/{local_author_directory,author_directory_factory}.py`, `api/http/{errors,etag,pagination,dependencies,health,wallpapers,router}.py`, `cli.py` (`python -m catalog.cli ensure-indexes`), `util/{clock,ids}.py`. Empty placeholders with docstrings: `security/`, `resilience/`, `jobs/`, `i18n/`, `api/grpc/`.
- Document shape follows README §6.3 (`_id` = `wp_<ULID>`, camelCase fields `assetId`, `favoriteCount`, `createdAt`, nested `author` snapshot, `version`). Status values: `PENDING_MEDIA`, `PUBLISHED`, `REJECTED`. Categories: `NATURE`, `ABSTRACT`, `CITY`, `SPACE`, `ANIMALS`, `MINIMAL`, `GAMES`, `OTHER` (the last two lists are our choice, the README only shows examples).
- Indexes (created by `just catalog-indexes`, never at startup): `ix_wallpapers_status_created`, `ix_wallpapers_category_created`, `ix_wallpapers_author_created`, `ix_wallpapers_tags`.
- Stand-in adapter: `LocalAuthorDirectory` invents an author snapshot from the id (`user-<first 8 chars>`). It replaces the account gRPC client until C5.
- Recipes: `catalog-sync | catalog-run | catalog-fix | catalog-check | catalog-indexes | catalog-test-integration`. They use `uv run --directory services/catalog/python-fastapi ...` and a `catalog_dir` variable, so they work from the repo root in any shell.
- Not yet built in catalog: authentication and ownership, DELETE and PUT, favorites, moderation, Elasticsearch, Redis, GraphQL, REST/gRPC clients, Kafka, i18n, correlation id, rate limiting, idempotency, resilience wrappers.

**notification-service (Phase 4, started 23 Oct 2026):** lives in `services/notification/python-fastapi/`, same layered layout as account (section 5), env prefix `NOTIFICATION_`, dev HTTP port **8083** (our choice, so it does not clash with account on 8080), Redis as the only store (logical database 0). Python: `requires-python >=3.14`, `.python-version` `3.14`. Like catalog, the first slice shipped its own `pyproject.toml` and `uv.lock` (new service). Slices are named **N1 - N7**, so they are not confused with account's Slice 4.

- `.env` next to its `pyproject.toml` (template `.env.example`): `NOTIFICATION_REDIS_URL=redis://localhost:6379/0` (required, no default). Optional: `NOTIFICATION_ENVIRONMENT` (`local|test|prod`), `NOTIFICATION_REDIS_CONNECT_TIMEOUT_SECONDS` (1.0), `NOTIFICATION_REDIS_COMMAND_TIMEOUT_SECONDS` (2.0), `NOTIFICATION_HEALTH_CHECK_TIMEOUT_SECONDS` (1.0). The settings file finds `.env` from its own location, so the service starts from any working directory.
- Delivered in N1: `main.py` (app factory `create_app(settings)` + lifespan: lazy Redis client and settings on `app.state`, `aclose()` on shutdown; start with `uvicorn notification.main:create_app --factory`), `config/settings.py` (`redis_url` required `SecretStr`, scheme validator for `redis://`, `rediss://`, `unix://`, positive timeouts), `infra/redis_client.py` (`create_redis_client`, `ping_redis`), `api/http/{router,health,dependencies,errors}.py`, `domain/exceptions.py` (`AppException` family and the `FieldViolation` dataclass), `dto/{base,problem,health}.py`. Empty placeholders with docstrings: `api/sse/`, `mapper/`, `repository/`, `security/`, `resilience/`, `jobs/`, `i18n/`, `util/`.
- Recipes: `notification-sync | notification-run [port=8083] | notification-fix | notification-check | notification-test-integration`. They use `uv --directory services/notification/python-fastapi ...` on one line each, so they work from the repo root in any shell and stop at the first failing line.
- Not yet built in notification: authentication, inbox and preferences (N2), events and templates (N3), email delivery (N4), live push (N5), digest (N6), Kafka consumers (N7), i18n, correlation id, rate limiting, resilience wrappers.

**Repo layout (key files):**

```text
wallpaper-hub/
  justfile  README.md  .gitignore  .gitattributes (LF endings)  .editorconfig
  contracts/  proto/account/v1/account.proto   avro/account.user.registered.v1.avsc
              i18n/{en,de,es}.json (29 keys each, since 4.1)   openapi/ graphql/ db-schema/ (empty so far)
  infra/  docker-compose.yml  .env.example  postgres/init/01-create-databases.sh
          mongo/init/01-create-catalog-user.js
          keycloak/realm-export.json
  services/account/python-fastapi/
    pyproject.toml  uv.lock  alembic.ini  .env.example  CHEATSHEET.md
    migrations/  env.py  script.py.mako  versions/ (0001 create users, 0002 align users with README)
    src/account/
      main.py                 app factory + lifespan (engine, session factory, shared httpx2 client,
                              token validator, identity provider on app.state)
      config/settings.py      pydantic-settings, env prefix ACCOUNT_ (database, oidc_*, identity provider, keycloak_*)
      api/http/               router, registrations, users (incl. /me), health, dependencies (get_current_user),
                              guards (require_permission / require_role / InternalDep), etag, errors (localized
                              since 4.1), responses + the /auth refresh and logout endpoints delivered in 3.7
      domain/                 user_service (incl. update_profile, compensation), exceptions (title_key,
                              message_key), identity (port)
      dto/                    base (camelCase), page, problem, user (incl. UpdateProfileRequest)
      i18n/                   negotiation (resolve_locale), messages (bundles, translate, find_bundle_dir)
      mapper/user_mapper.py
      repository/             models, database, user_repository
      security/               jwks (async key cache), jwt_validator, current_user, permissions (role -> permission
                              table), authorization (ownership), errors (TokenRejected 401 / JwksUnavailable 503)
      infra/                  local_identity (stand-in), keycloak_identity (admin API client), identity_factory
      util/                   pagination, clock
      resilience/ jobs/ api/grpc/   empty placeholders with docstrings
    tests/  unit/ (conftest, health, settings, pagination, mappers, api_errors, i18n, jwt_validator, current_user,
                   auth_dependency, etag, keycloak_identity, identity_settings, security/{conftest,permissions,guards})
            integration/ (conftest with the auth_headers fixture, database, users_api, profile_api,
                          registration_compensation, keycloak_registration)
  services/media/python-fastapi/     (see the media-service paragraph above)
  services/catalog/python-fastapi/
    pyproject.toml  uv.lock  .python-version  .env.example  CHEATSHEET.md
    src/catalog/
      main.py  cli.py
      config/settings.py
      api/http/               router, wallpapers, health, dependencies, etag, pagination, errors
      domain/                 models, exceptions, ports (WallpaperStore, AuthorDirectory), wallpaper_service
      dto/                    base, page, problem, wallpaper
      mapper/wallpaper_mapper.py
      repository/             database, documents, wallpaper_repository, indexes
      infra/                  local_author_directory, author_directory_factory
      util/                   clock, ids
      security/ resilience/ jobs/ i18n/ api/grpc/   empty placeholders with docstrings
    tests/  unit/ (conftest with InMemoryWallpaperStore, settings, health, etag, pagination, documents,
                   wallpapers_api, app_lifespan)
            integration/ (conftest with a clean catalog_test collection per test, wallpaper_repository,
                          indexes, catalog_api_mongo)
  services/notification/python-fastapi/
    pyproject.toml  uv.lock  .python-version  .env.example  CHEATSHEET.md  README.md
    src/notification/
      main.py                 app factory + lifespan (Redis client and settings on app.state)
      config/settings.py      env prefix NOTIFICATION_, required redis_url (SecretStr)
      api/http/               router, health (live, ready), dependencies (RedisDep, SettingsDep), errors
      domain/exceptions.py    AppException family + FieldViolation
      dto/                    base (camelCase), problem, health
      infra/redis_client.py   create_redis_client, ping_redis
      api/sse/ mapper/ repository/ security/ resilience/ jobs/ i18n/ util/   empty placeholders with docstrings
    tests/  unit/ (conftest with FakeRedis and the make_settings / settings / app / client / fake_redis fixtures,
                   health, settings, errors)
            integration/ (conftest with real_settings and redis fixtures, redis_integration)
```

**Just recipes:** `infra-up | infra-down | infra-reset | infra-ps | infra-logs [service]`; `account-sync | account-run | account-fix | account-check | account-migrate | account-migration 'message' | account-test-integration`; `media-*` (see above); `catalog-sync | catalog-run | catalog-fix | catalog-check | catalog-indexes | catalog-test-integration`; `notification-sync | notification-run [port] | notification-fix | notification-check | notification-test-integration`. First run: copy `infra/.env.example` to `infra/.env`, then `just infra-up`.

**Runtime deps:** fastapi, uvicorn\[standard\], pydantic-settings, sqlalchemy\[asyncio\], asyncpg, alembic, email-validator, pyjwt\[crypto\] (token validation; its `cryptography` is also used by tests), httpx2 (JWKS download and Keycloak admin API; FastAPI's TestClient needs it too). Step 4.1 added no dependency. **Dev deps:** pytest, pytest-asyncio, ruff, pyright. The import name is `httpx2`. **Catalog** (own `pyproject.toml`): fastapi, uvicorn\[standard\], pydantic-settings, pymongo (async API: `AsyncMongoClient`), python-ulid, httpx2 (for TestClient; becomes a real dependency with the C5 clients); dev: pytest, pytest-asyncio, ruff, pyright. **Notification** (own `pyproject.toml`): fastapi, uvicorn\[standard\], pydantic-settings, redis (redis-py, async API `redis.asyncio`); dev: pytest, pytest-asyncio, ruff, pyright, httpx2 (FastAPI's TestClient needs it).

**Endpoints now (account):**

| Endpoint | Access | Notes |
| --- | --- | --- |
| `GET /health/live`, `GET /health/ready` | public | ready is 503 if the DB is down |
| `POST /api/v1/registrations` | public | 201 + Location; creates the Keycloak user when `ACCOUNT_IDENTITY_PROVIDER=keycloak` (users.id = Keycloak `sub`); with `local` it invents an id and discards the password |
| `GET /api/v1/users` | permission `user:list` (ADMIN) | paged, whitelisted sort, full view |
| `GET /api/v1/users/me` | permission `profile:read` | full view + `ETag` header |
| `PATCH /api/v1/users/me` | permission `profile:write` | partial update of displayName, bio, locale; needs `If-Match` (428 missing, 412 stale); unknown fields are a 400 |
| `GET /api/v1/users/{id}` | any signed-in caller | public view, no email |
| `DELETE /api/v1/users/{id}` | owner or `user:delete` (ADMIN) | soft delete, then disables the Keycloak login (best effort) |
| `POST /auth/refresh`, `POST /auth/logout` | public | delivered in 3.7, via Keycloak's token endpoints; path prefix and request shapes: see that delivery |

Router-level default: every route in `users.py` requires a valid token, so a new route there is protected unless it opts out on purpose. Since 4.1 every error response honors `Accept-Language` (en, de, es) and carries a `Content-Language` header.

**Endpoints now (catalog, all PUBLIC until C2 adds authentication):**

| Endpoint | Notes |
| --- | --- |
| `GET /health/live`, `GET /health/ready` | ready pings MongoDB, 503 problem+json when it is down |
| `POST /api/v1/wallpapers` | body `title`, `description`, `tags` (max 10, trimmed, lowercased, unique), `category`, `assetId` (`ast_...`), **temporary** `authorId`; 201 + `Location` + `ETag`; status starts as `PENDING_MEDIA` |
| `GET /api/v1/wallpapers` | `page`, `size` (clamped to 100), `sort` (`createdAt`, `updatedAt`, `title`, `favoriteCount`; `<field>,<asc\|desc>`), filters `status`, `category`, `tag`, `authorId`; envelope `items/page/size/totalItems/totalPages`; no default status filter yet |
| `GET /api/v1/wallpapers/{id}` | full document view + `ETag`; malformed id is 400, unknown id 404 |
| `PATCH /api/v1/wallpapers/{id}` | partial update of `title`, `description`, `tags`, `category`; needs `If-Match` (428 missing, 412 stale or weak, 400 malformed, `*` accepted); an empty body is 400; `null` counts as 'not sent' |

**Endpoints now (notification, all PUBLIC; N1 has only health):**

| Endpoint | Notes |
| --- | --- |
| `GET /health/live` | always `{"status":"UP"}` while the process runs; never touches Redis |
| `GET /health/ready` | pings Redis within `NOTIFICATION_HEALTH_CHECK_TIMEOUT_SECONDS`; 200 `{"status":"UP","checks":{"redis":"UP"}}` or 503 `{"status":"DOWN","checks":{"redis":"DOWN"}}`. The 503 body is a health report on purpose, not problem+json, and never contains error details |
| any unknown path or wrong method | problem+json 404 or 405 |

## 5. Code conventions (new code must match)

- **Layers:** `api/http` (routers, dependencies, error handlers) -> `domain` (services, exceptions, ports) -> `repository` (SQL, or MongoDB in catalog, or Redis in notification). DTOs in `dto/`, explicit field-by-field mappers in `mapper/`. Domain code never builds HTTP responses and never imports DTOs (notification's `FieldViolation` dataclass lives in `domain/exceptions.py`; the error handler maps it to the `FieldError` DTO).
- **Transactions:** one `AsyncSession` per request via `Depends(get_session)`. Services commit; repositories only flush. Unique violations are translated to 409 using constraint names (`uq_users_username`, `uq_users_email`). (Catalog has no multi-document transactions: single-document atomic operations such as `find_one_and_update` give the same safety for one wallpaper.)
- **JSON:** camelCase on the wire (all DTOs inherit `ApiModel`), snake\_case in Python. Passwords are `SecretStr`. In catalog, request DTOs inherit `ApiRequest` (camelCase names only, unknown fields rejected); response DTOs inherit `ApiModel`.
- **Errors:** raise `AppException` subclasses (`ValidationException` 400, `UnauthorizedException` 401, `ForbiddenException` 403, `NotFoundException` 404, `ConflictException` 409, `PreconditionFailedException` 412, `PreconditionRequiredException` 428, `ServiceUnavailableException` 503; add 413/415/429 as needed). An exception can carry response `headers` (used for `WWW-Authenticate`). One set of handlers in `api/http/errors.py` returns RFC 9457 `application/problem+json` with `type` (`https://wallpaperhub.dev/problems/<slug>`), `title`, `status`, `detail`, `instance`, `errors[{field, code, message}]`. Validation is 400 (not 422). Codes: Required, Size, Pattern, Email, Range, InvalidValue, InvalidFormat, MalformedJson, AlreadyExists. Unexpected errors return a generic 500. Catalog and notification follow the same shape, also for unknown routes (404) and wrong methods (405). Notification's `AppException` carries `code` (the problem slug, later the i18n message key), `status` and `title`; it has no `Email` code yet (no `email-validator`) and no 412/428 yet; both arrive when first needed.
- **Localization (account, since 4.1; the template for the other services):** code never writes user-facing sentences for new errors, it passes a key. `AppException(detail, ..., message_key=..., message_args=...)` and `FieldIssue(field, code, message, message_key=..., message_args=...)`; `detail` / `message` stay as the English fallback and for logs. Every `AppException` subclass must set `title_key` (`error.<name>.title`) and the key must exist in all three bundles, otherwise it inherits its parent's title. Bundle keys are flat and dotted (`validation.size.min`), placeholders are `{name}`, every language file has the same keys and the same placeholder names (tests enforce it). Handlers get the language with `request_locale(request)` and translate with `translate(key, locale, **args)`; problem responses carry `Content-Language`. A new pydantic error type gets a branch in `_message_key_for` in `errors.py`.
- **Config:** `Settings` (env prefix `ACCOUNT_` / `MEDIA_` / `CATALOG_` / `NOTIFICATION_`, `.env` next to pyproject), required connection setting has no default (fail fast), cached `get_settings()`. Pyright needs `# pyright: ignore[reportCallIssue]` on `Settings()` calls. Validators fail fast on bad combinations: `identity_provider=keycloak` needs `keycloak_client_secret`, and stand-in providers (`local`) are refused when `environment=prod`. Notification resolves the `.env` path from `__file__` (absolute), so it works from any working directory, and unit tests build `Settings(_env_file=None, ...)` so a real `.env` is never read. Exception: account's i18n bundle folder is read from `os.environ["ACCOUNT_I18N_DIR"]` in `i18n/messages.py`, not from `Settings` (move it into `Settings` with the layered config in 11.3 if desired).
- **Lifespan:** creates engine (or Mongo client, or Redis client), session factory, one shared `httpx2.AsyncClient` (JWKS download and Keycloak admin API), token validator and identity provider (via `create_identity_provider`) on `app.state`; the HTTP client is closed and the engine disposed on shutdown. The service starts even if Postgres, MongoDB, Redis or Keycloak is down: signing keys and admin tokens are fetched on first use, the Mongo and Redis clients connect lazily; readiness reports the database. Type the lifespan as `AsyncGenerator[None]` (Pyright strict flags `AsyncIterator[None]` with `@asynccontextmanager` as deprecated). Services that are started with `uvicorn <module>:create_app --factory` have no module-level `app`, so importing them never needs settings.
- **Ports and stand-ins (catalog, C1):** whatever the domain needs from outside is a `Protocol` in `domain/ports.py` (`WallpaperStore`, `AuthorDirectory`). The real adapter lives in `repository/` or `infra/`; a local stand-in lets the service run alone until the other service exists, selected by a setting and refused in prod. Unit tests use fakes with the same contract as the real adapter (`InMemoryWallpaperStore`). Notification uses the same approach for Kafka, the account gRPC client and the catalog client (N3, N6, N7).
- **MongoDB (catalog):** documents use README §6.3 field names; `repository/documents.py` translates explicitly in both directions. Sorting always adds `_id` as a tie-breaker so pages are stable. Optimistic locking uses one atomic `find_one_and_update` filtered on `{_id, version}` with `$inc: {version: 1}`. Datetimes are timezone-aware UTC, cut to milliseconds (`utc_now()`), because MongoDB stores milliseconds. Indexes are created by an explicit command, never at startup, like migrations.
- **Redis (notification, N1):** one shared async client from `create_redis_client(settings)` in `infra/redis_client.py`, with `decode_responses=True` (Redis returns `str`, not bytes) and explicit connect and command timeouts. The readiness probe `ping_redis(client, timeout_seconds)` wraps `PING` in `asyncio.timeout(...)`, never raises, returns a bool and logs only the exception class name. redis-py types its keyword arguments loosely, so Pyright strict needs `# pyright: ignore[reportUnknownMemberType]` on calls such as `Redis.from_url`, `ping`, `get`, `set`, `ttl`, `keys`, `delete`. Application code must use `SCAN`, never `KEYS`; only test cleanup uses `KEYS` on the dev database.
- **Input normalization (catalog):** normalize in a `BeforeValidator` so the pattern check sees the cleaned value (pydantic runs `pattern` before `strip_whitespace`/`to_lower`). Paging: `size` above 100 is clamped, below 1 or a negative `page` is a 400 `Range`; `sort` must be whitelisted per endpoint, otherwise 400 on field `sort`.
- **Security:** (README §7)
  - Token validation order: header and algorithm allow-list (RS256 only, never trust the token's `alg`), `kid` -> cached key (reload on unknown `kid`, throttled to one per 30 s, stale keys kept if Keycloak is down), then signature, `iss`, `aud`, `exp`/`nbf` with leeway, required claims, `typ=Bearer`. The precise rejection reason goes to the log only; the client always gets the same generic 401 message.
  - Answers: no token 401 + `WWW-Authenticate: Bearer`; bad token 401 + `Bearer error="invalid_token"`; valid token but not allowed 403 (never says which permission was missing); Keycloak keys unavailable 503.
  - Code checks permissions, not role names: the `Permission` enum and the role table live in `security/permissions.py`; guards are `require_permission(...)`, `require_role(...)`, `InternalDep`. Ownership: `ensure_owner_or_permission(...)`, called BEFORE the database lookup so a stranger gets 403 whether or not the id exists.
  - Optimistic locking over HTTP: strong ETag `"<version>"`, `If-Match` required on PATCH (428 missing, 412 stale or weak, `*` accepted, 400 malformed). A save between read and commit is caught by the `version` column (`StaleDataError` -> 412; in catalog the atomic version filter returns no match -> 412). Body validation (400) runs before the `If-Match` check. `/users/me` must be declared before `/users/{user_id}`.
  - Identity provider port: `create_user`, `delete_user`, `disable_user`. Registration undoes the Keycloak user if the DB step fails (compensating action; a failed cleanup is logged, never masks the original error). Deleting an account disables the Keycloak login. The Keycloak client uses an `account-svc` client-credentials token (cached, renewed 30 s before expiry, one retry on 401) and needs exactly `manage-users` and `view-realm`.
  - Use `http.HTTPStatus` for status comparisons: `httpx2.codes.X` is not an int enum.
- **Migrations:** Alembic async env reads the same Settings. Naming convention for constraints. Ruff post-write hooks tidy new files. Autogenerate, then review by hand; CHECK constraints are written manually. `uv run alembic check` must say 'No new upgrade operations detected'. Migrations run as a separate step, never at startup. (Catalog has no migrations tool yet: indexes come from `just catalog-indexes`. Notification has no schema: Redis keys are created by the code that uses them.)
- **Tests:** unit tests run without DB (`tests/unit/conftest.py` sets env, so a real `.env` is never read) and fake dependencies with `app.dependency_overrides` or `monkeypatch`. Integration tests are marked `integration`, skipped by default (`addopts = -m 'not integration'`), run with `just account-test-integration` (a later `-m integration` on the command line overrides the default; verified). Test users are named `it_xxxxxxxx` and hard-deleted after each test (database rows by the autouse fixture; Keycloak users by the live-Keycloak test module).
  - Catalog integration tests use the database `catalog_test` and drop the `wallpapers` collection before and after every test; they stop with a clear message when MongoDB is unreachable or rejects the credentials. Run them on their own (`pytest tests/integration -m integration`, which the recipe does), because the unit conftest sets a fake URI.
  - Notification unit tests replace Redis with `FakeRedis` (answers PING, fails, or answers too slowly) through the `fake_redis(error=..., delay_seconds=...)` fixture and `app.dependency_overrides[get_redis]`; settings come from the `make_settings(**overrides)` factory fixture. Shared test helpers are **fixtures in `conftest.py`**: the test folders are not Python packages, so `from tests.unit.conftest import ...` fails. Notification integration tests use the real Redis from `.env`, name their keys `it:<uuid>` and delete them afterwards; they fail with a clear message ('start it with `just infra-up`') when Redis is down or `NOTIFICATION_REDIS_URL` is missing. Integration tests also include one that points the real client at a closed port and expects 503.
  - Auth tests do not need Keycloak: unit tests generate their own RSA key and serve a fake JWKS (`tests/unit/security/conftest.py`, `auth_headers` fixture); the integration fixture `auth_headers` in `tests/integration/conftest.py` swaps the running app's token validator for one that trusts a key made by the test run.
  - `tests/integration/test_keycloak_registration.py` talks to the real Keycloak: it skips itself when Keycloak is not running and FAILS (with instructions) when it runs with an outdated realm file.
  - i18n tests (`tests/unit/test_i18n.py`) use a tiny throwaway FastAPI app with the real `register_exception_handlers`, so they need no database; a parity test compares the key sets and the placeholder names of the three JSON bundles.
  - Async tests carry `@pytest.mark.asyncio` (or a module `pytestmark`) explicitly, so they work in both pytest-asyncio modes; test files in different folders must have different names. Mocked Keycloak calls in unit tests use `httpx2.MockTransport`. Async Mongo fixtures are function-scoped (the async client is tied to the event loop of the test). Async fixtures in strict mode use `@pytest_asyncio.fixture`.
- **Tooling:** Ruff line length 100, rules E F I UP B SIM ASYNC S N C4 PT RUF FAST (tests may use assert and fake passwords; `AppException` needs `# noqa: N818` because the README fixes that name). Pyright strict on `src` and `tests`. Do not enable Ruff's TC rules (they break FastAPI/Pydantic runtime annotations). FastAPI rule FAST001: do not repeat `response_model` when the return type annotation says it. pydantic-settings' `_env_file` argument is unknown to Pyright: put `# pyright: ignore[reportCallIssue]` on that call line.
- **Windows notes:** PowerShell, `curl.exe` (not `curl`), LF line endings enforced by `.gitattributes`, asyncpg chosen because async psycopg needs a different event loop on Windows, SIGTERM behaves differently so test graceful shutdown in a container. Just recipes that need another working directory use `uv --directory <dir> ...` (or `uv run --directory`) on one line each, not `cd x; cmd`.
- **Docs:** add a row to `CHEATSHEET.md` (concept -> file) for every new concept. (4.1 rows to add if not yet there: language negotiation `i18n/negotiation.py`; message keys and bundles `i18n/messages.py`; localized problem+json `api/http/errors.py`; key-parity test `tests/unit/test_i18n.py`.)

## 6. Roadmap

Step numbers (3.1, 3.2 ...) are the bookmarks: tell Claude the last finished step. Pull-forward tip: after Slice 3, do steps 11.1, 11.4 and 11.5 early (Dockerfile, pre-commit, CI) so every later slice is checked automatically.

### Phase 1: account-service (the template)

**Slice 3 - Authentication and authorization (README §7, §5.1)** - concepts: JWT, JWKS, OAuth2 client credentials, HTTP conditional requests

- ✅ 3.1 JWT validation: signature via cached JWKS (refetch on unknown key id), `iss`, `aud=account-svc`, `exp`/`nbf` with leeway, `typ=Bearer`. New settings for issuer and JWKS URL.
- ✅ 3.2 `CurrentUser` dependency (sub, email, locale, realm roles, scope); 401 problem+json with `WWW-Authenticate`; 503 when the key set cannot be loaded.
- ✅ 3.3 Authorization layers: public / authenticated / internal-only; role dependencies; role-to-permission map; ownership helper.
- ✅ 3.4 Protect routes: `GET /users` ADMIN only, `DELETE` ADMIN or owner, registration public, `GET /users/{id}` authenticated. Router-level default-deny; integration tests log in with a fake identity provider.
- ✅ 3.5 `GET` and `PATCH /users/me` with ETag + `If-Match` (428 missing, 412 mismatch) using the existing `version` column. Documented 401/403/412/428 responses in OpenAPI.
- ✅ 3.6 Real Keycloak admin client behind the `IdentityProvider` port: client-credentials token cached and refreshed, create user (password set at creation), assign USER, compensate (delete in Keycloak) if the DB insert fails, disable the Keycloak user when an account is deleted. Settings switch local/keycloak. Realm file updated (see section 4).
- ✅ 3.7 `POST /auth/refresh` and `/auth/logout` (educational): public endpoints that pass through to Keycloak's token endpoints, plus refresh-token inspection.
- ⬜ 3.8 Tests: consolidate and extend. (a) One shared fake-identity helper: today the RSA-key/fake-JWKS code exists in `tests/unit/security/conftest.py`, `tests/unit/test_jwt_validator.py`, `tests/unit/test_auth_dependency.py`, `tests/integration/conftest.py` and `tests/integration/test_users_api.py` (and will be copied into media M2, catalog C2 and notification N2). (b) Integration tests with real Keycloak tokens for `alice`, `mod` and `admin-demo`: a role/permission matrix over the real endpoints. (c) Keep the unit tests with locally generated RSA keys and a fake JWKS. Still deferred while Slice 4 is in progress.

**Slice 4 - Cross-cutting API behavior (README §5.2, §8 inbound, §12 middleware order)** - concepts: middleware, Redis, ordering

- ✅ 4.1 i18n (delivered 23 Oct 2026 as `account-slice4-i18n.zip`, confirmed green by the user): `Accept-Language` -> en/de/es; message lookup from `contracts/i18n` with placeholders; `title`, validation `detail` and `errors[].message` localized; `Content-Language` on error responses; key-parity and placeholder-parity tests. Details: section 4 ('account i18n'). Left to the user: converting the hard-coded English exception `detail` strings to keys (find them with `rg -n "Exception\(" src`).
- ⬜ 4.2 Correlation id middleware (`X-Request-ID`), structured JSON logging, request logging, PII masking util. **Agreed design (23 Oct 2026, not yet built):** Python's `logging` only (no new dependency); pure ASGI middleware (not `BaseHTTPMiddleware`, which loses `contextvars`); correlation id accepted from the incoming `X-Request-Id` only if it matches `[A-Za-z0-9._-]{8,64}`, otherwise generated (UUID v7), echoed in the response header and kept in a `contextvars` variable; JSON log lines with `timestamp`, `level`, `logger`, `message`, `service`, `correlation_id`, `user_id`; one request log line per request with method, path, status and duration only (never query string, headers or bodies); uvicorn's own access log switched off (our request log replaces it) and its other loggers routed through the same JSON format; settings `ACCOUNT_LOG_LEVEL` and `ACCOUNT_LOG_FORMAT=json|console`; the user id is put into the log context in `get_current_user` after authentication; `util/pii.py` masks emails (`a***@example.com`) and tokens; `trace_id` / `span_id` come with OpenTelemetry in 9.2. Planned files: new `util/pii.py`, `util/logging_setup.py`, `api/http/middleware.py`; edits to `config/settings.py`, `main.py`, `api/http/dependencies.py`, the `account-run` recipe (add `--no-access-log`); tests `test_pii.py`, `test_logging.py`, `test_correlation_middleware.py`; zip name `account-slice4-logging.zip`. Needs from the user: `main.py`, `config/settings.py`, `api/http/dependencies.py`, `tests/unit/conftest.py` and the `account-run` recipe lines from `justfile`.
- ⬜ 4.3 Redis (async client, readiness check) and token-bucket rate limit on registration -> 429 + `Retry-After`; add an `error.rateLimited.*` detail key (the title key already exists). (Notification N1 already contains a Redis client and readiness probe to copy.)
- ⬜ 4.4 `Idempotency-Key` on POST with results stored at `idem:{key}`.
- ⬜ 4.5 CORS (expose the `ETag` and `Location` headers, otherwise browser code cannot read them), security headers, gzip, body-size limit; final middleware order: correlation-id, logging, locale, rate limit, auth, idempotency, compression/CORS/headers. (Locale is already resolved inside the error handlers since 4.1; a locale middleware is only needed if something other than error handlers must know the language.)

**Slice 5 - Redis cache (README §6.5)**

- 5.1 Cache-aside for `GET /users/{id}` at `cache:user:{id}`. 5.2 TTL with jitter and single-flight stampede protection. 5.3 Invalidate on update/delete. 5.4 Hit/miss counters (feed `cache_hit_ratio` later). 5.5 Tests.

**Slice 6 - Transactional outbox and Kafka (README §4.3, §5.6, §9, §6.1)** - concepts: outbox pattern, Avro, schema registry, idempotent producers

- 6.1 Add Kafka (KRaft) and Schema Registry to the `infra` profile; topics `account.user.registered.v1`, `account.user.profile-updated.v1`, `account.user.deleted.v1`.
- 6.2 `outbox_event` table + migration; events written in the same transaction as the change (register, profile update, avatar/banner, delete).
- 6.3 Avro schemas for all three events in `contracts/avro` plus a compatibility check.
- 6.4 Relay job: poll every 500 ms, batches of 100, serialize Avro at publish time, idempotent producer `acks=all`, set `published_at`, count `attempts`, backoff, Redis distributed lock so one instance runs.
- 6.5 Daily jobs: outbox cleanup, purge soft-deleted users after 30 days.
- 6.6 `PUT /users/me/avatar` and `/users/me/banner` with body `{assetId}` plus the profile-updated event.
- 6.7 Tests: relay unit tests; Kafka integration; broker down then up failure test.

**Slice 7 - gRPC server and management port (README §5.4, §12)**

- 7.1 Generate Python stubs from `contracts/proto` (a `just proto` recipe). 7.2 Servicer: `GetUser`, `GetUsersByIds`, streaming `ListUsersUpdatedSince`. 7.3 Interceptors: auth (service token with role `internal`; service-account tokens carry no `aud` today, so add an audience mapper to the service clients in the realm first), error-to-status mapping, logging. 7.4 Management app on 8081: `/health/live`, `/ready`, `/startup` moved there, optional `/metrics`. 7.5 Run HTTP 8080 + management 8081 + gRPC 9090 in one event loop with graceful shutdown. 7.6 In-process gRPC tests.

**Slice 8 - Audit log (README §11)**

- 8.1 `audit_log` table + migration. 8.2 SQLAlchemy event listeners record before/after JSON, actor, trace id. 8.3 Tests.

**Slice 9 - Observability (README §11)**

- 9.1 `observability` compose profile: Alloy, Loki, Tempo, Prometheus, Grafana with provisioning. 9.2 OpenTelemetry SDK: traces (FastAPI, SQLAlchemy, Redis, Kafka), logs with trace/span ids, OTLP metrics. 9.3 Add `traceId` to problem+json. 9.4 Business metrics (`outbox_pending`, `outbox_oldest_age_seconds`, `cache_hit_ratio`). 9.5 RED dashboard and trace-log correlation.

**Slice 10 - Resilience (README §8)**

- 10.1 `resilience/` wrappers: timeout, retry with backoff + jitter, circuit breaker, bulkhead, rate limiter. 10.2 Apply to the Keycloak client, token provider, relay backoff. 10.3 Unit tests of each policy; `circuit_breaker_state` metric.

**Slice 11 - Production hardening and delivery (README §12, §13)**

- 11.1 Dockerfile: multi-stage uv build, non-root user, healthcheck, `.dockerignore`, `contracts/i18n` bundled into the image with `ACCOUNT_I18N_DIR` pointing at it. 11.2 Compose `apps` profile and a one-shot migrate command. 11.3 Layered config (defaults -> profile local/test/prod -> env -> secret files). 11.4 pre-commit. 11.5 GitHub Actions gates: ruff, format check, pyright, unit, integration, Avro compatibility, OpenAPI diff. 11.6 Export the golden OpenAPI spec to `contracts/openapi`. 11.7 Graceful-shutdown test; Keycloak `start --optimized` notes.

**Slice 12 - Close-out of Phase 1**

- 12.1 Full test pyramid (move integration tests to Testcontainers where sensible, add contract tests). 12.2 Finish `CHEATSHEET.md`. 12.3 e2e skeleton hooks. 12.4 Check against README §16 coverage matrix. 12.5 Write 'template notes': what to copy into future projects.

### Phase 2: media-service (README §3, §5.1, §6.2, §9, §10)

Slice names are M1-M7. Same delivery protocol (section 7), zip names `media-slice-mN-<topic>.zip` extracted over the repo root, replacing files only inside `services/media/python-fastapi/`.

- ✅ M1 Skeleton: settings, DB engine, tables and migration 0001, health, problem+json errors, tests, recipes.
- ⬜ M2 Security and metadata API (README §7, §5.1): copy account's `security/` (JWKS cache, validator, `CurrentUser`, permissions, ownership) with `aud=media-svc` (setting `MEDIA_OIDC_AUDIENCE`); `GET /media` (own assets, paged, whitelisted sort), `GET /media/{id}`, `DELETE /media/{id}` (metadata only; S3 cleanup arrives in M6). Ownership check before the DB lookup. Needs from the user: account's `security/` folder and `api/http/dependencies.py`.
- ⬜ M3 Upload and storage (README §10 steps 1-2, §5.1): MinIO in compose (`infra/` is user-owned: deliver compose and `minio-init` changes separately), S3 port + aioboto3 adapter, `POST /media` multipart with size limit (413), magic-byte sniffing (415) and pixel cap, original stored privately, response **202** `PROCESSING`, `GET /media/{id}/url` (presigned). Verify the aioboto3 version first.
- ⬜ M4 Queue and worker (README §9): Redis job queue, separate worker process, retries then dead-letter, enqueue after commit (known gap: crash between commit and enqueue leaves `PROCESSING`; M6 requeues). Recommended library: taskiq with its Redis broker (arq is in maintenance-only mode); verify the current version before pinning. Redis can now be verified natively in the sandbox.
- ⬜ M5 Image pipeline (README §10 steps 3-9): EXIF orientation then strip, sRGB, SHA-256 + perceptual hash, blurhash + palette, variants per purpose with `Cache-Control: immutable` under `{purpose}/{yyyy}/{mm}/{assetId}/{variant}.webp`, `READY` or `REJECTED`, `EventPublisher` port with a logging adapter (Kafka adapter arrives with account step 6.1), CHECK on `media_variant.kind`. Verify Pillow, imagehash and blurhash versions first (Pillow 12.x supports Python 3.14).
- ⬜ M6 Scheduled jobs (README §9): hourly orphan cleanup and requeue of stuck `PROCESSING` assets behind a Redis `lock:{job}`, S3 `DeleteObjects` batches of up to 1000 keys. Scheduler library to be chosen then (APScheduler or the queue's own scheduler).
- ⬜ M7 Close-out: S3 timeout/retry policy (README §8: 10 s, 3 retries), remaining tests, CHEATSHEET, notes on what moves to Kafka and what to port from account's cross-cutting slices (i18n from account 4.1, correlation id from 4.2, rate limit on upload).

Design notes: media publishes events directly after commit with no outbox on purpose (README decision #4, the contrast to account). Services do not share code, so some duplication with account is accepted and listed in the close-out.

### Phase 3: catalog-service (README §3, §4.1, §5.1, §5.5, §5.6, §6.3 - 6.5, §8, §9)

Slice names are C1-C7. Same delivery protocol (section 7), zip names `catalog-sliceCN-<topic>.zip` extracted over the repo root, replacing files only inside `services/catalog/python-fastapi/`. Everything the service needs from other services (account gRPC, media REST, Kafka events) sits behind a port with a local stand-in, so catalog runs alone and the real adapters are swapped in later (same idea as account's `IdentityProvider`). Stand-ins are refused when `environment=prod`.

- ✅ C1 Skeleton and Mongo CRUD (README §5.2, §5.3, §6.3, §12): service skeleton in the account layout, Mongo in compose (init script, `infra/.env` lines, `mongo-data` volume), wallpaper create/get/list/patch with paging, whitelisted sort and filters, ETag + `If-Match`, atomic version check in MongoDB, indexes by command, problem+json errors, readiness that pings MongoDB, author snapshot from the `LocalAuthorDirectory` stand-in. Sandbox: 67 unit + 16 integration tests (real MongoDB 8.3.7, also with authentication on), live curl smoke test, clean-extract check of the zip; the user then confirmed all green.
- ⬜ C2 Security and ownership (README §7): copy account's `security/` (JWKS cache, validator, `CurrentUser`, permissions, ownership) with `aud=catalog-svc`; remove the temporary `authorId` field (owner = token `sub`); `DELETE` and `PUT` on a wallpaper; owner or MODERATOR rules (ownership checked before the DB lookup); favorites; moderation endpoint (status `PUBLISHED`/`REJECTED`); public callers only see `PUBLISHED` by default. Needs from the user: account's `security/` folder and `api/http/dependencies.py`. Decide here whether to do account 3.8 first (third copy of the fake-JWT helpers).
- ⬜ C3 Search (README §6.4, §5.2 keyset pagination): Elasticsearch in compose (user-owned files delivered separately), index `wallpapers-v1` behind an alias, mapping, indexing on create/update/status change, search with filters, facets, autocomplete, and the endpoint that offers keyset (cursor) pagination. Verify the Elasticsearch image tag and `elasticsearch-py` version first; probe whether the sandbox can run Elasticsearch natively, otherwise those tests stay unverified until the user runs them.
- ⬜ C4 Redis (README §6.5): cache-aside for wallpaper reads, view/download counters, HyperLogLog for unique viewers, trending, flush job for counters (needs `jobs/`). Redis can be verified natively in the sandbox (Redis 8.8.3 build from N1), but redis-py usage should follow notification's `infra/redis_client.py`.
- ⬜ C5 Upstream clients and resilience (README §4.1, §5.4, §8): account gRPC client (author snapshot, replaces `LocalAuthorDirectory`) and media REST client (asset check, client-credentials token) behind the existing ports; timeout, retry with backoff, circuit breaker in `resilience/`; `httpx2` becomes a runtime dependency; setting `author_directory=grpc`. Needs account Slice 7 for the real server; until then the stand-in stays the default and gRPC is tested in-process.
- ⬜ C6 GraphQL (README §5.5): Strawberry schema, Relay connections, DataLoader for the author field (batched `GetUsersByIds`), error formatter with `extensions.code` from the exception model, auth in the context.
- ⬜ C7 Kafka consumers and producer (README §5.6, §9): consume `account.user.profile-updated.v1` (refresh author snapshots) and `account.user.deleted.v1`, `media.asset.processed` (fills variants, dimensions, palette, blurhash; status `PENDING_MEDIA` -> `PUBLISHED`); retry topics and DLQ, error classification retryable/non-retryable; idempotent handling. Deferred until account Slice 6 and media M5 exist (Kafka is unverified in the sandbox).
- Cross-cutting items catalog ports later from account's Slice 4 and 9-11: i18n (copy account's `i18n/` package and the bundles; delivered in account 4.1), correlation id and logging (account 4.2), rate limit, `Idempotency-Key`, CORS, observability, Dockerfile and CI. Close-out of Phase 3 lists what was duplicated.

### Phase 4: notification-service (README §3, §4.1, §4.4, §5.1, §5.6, §6.5, §7, §8, §9, §12 - 14)

Slice names are N1-N7 (so they are not confused with account's Slice 4). Same delivery protocol (section 7), zip names `notification-sliceN<k>-<topic>.zip` extracted over the repo root, replacing files only inside `services/notification/python-fastapi/`. The service depends on things that do not exist yet (Kafka and Schema Registry from account step 6.1, of the Avro schemas only `account.user.registered.v1` exists, the account gRPC server from Slice 7, the catalog REST API), so it is built around **ports with fakes**: events enter through `POST /admin/notifications/test` (ADMIN, README §5.1) until the real Kafka consumer arrives last (N7). Exact Redis key names and TTLs: README §6.5.

- ✅ N1 Skeleton and Redis connection (README §12, §6.5): service skeleton in the account layout (app factory, lifespan, typed settings with required `NOTIFICATION_REDIS_URL`), lazy async Redis client, `/health/live` and `/health/ready` (503 when Redis is down, no error details in the body), problem+json errors for every failure (exception model, 400 validation codes, 404/405, generic 500), tests, just recipes. Sandbox: 39 unit + 4 integration tests against a native Redis 8.8.3 built from source, Ruff and Pyright strict clean, live uvicorn smoke test with Redis up, stopped and back up (readiness 200, 503, 200; no tracebacks), clean-extract check of the zip with the exact `uv --directory` commands; the user then confirmed all green.
- ⬜ N2 Authentication, inbox and preferences (README §5.1, §6.5, §7): copy account's `security/` (JWKS cache, validator, `CurrentUser`, permissions, ownership) with `aud=notification-svc` (setting `NOTIFICATION_OIDC_AUDIENCE`); Redis storage for notifications (one hash per notification) and the per-user inbox (a sorted set per user); `GET /notifications` (paged, own notifications only), `POST /notifications/{id}/read`, `GET` and `PUT /notification-preferences`. Ownership check before the lookup. Needs from the user: account's `security/` folder and `api/http/dependencies.py` (fourth copy of the fake-JWT test helpers: see account 3.8).
- ⬜ N3 Events in, localized content (README §4.1, §5.6, §5.2 i18n): domain event types and an event handler per type behind a port; dedupe by event id with a TTL so redelivery creates no second notification; en/de/es notification texts and email templates from `contracts/i18n` (reuse account's `i18n/` package, delivered in account 4.1; `email.welcome.subject` already exists in the bundles); `POST /admin/notifications/test` (ADMIN) to feed events in without Kafka.
- ⬜ N4 Email delivery (README §8, §9): mail-provider port; SMTP adapter to Mailpit (already in compose); Redis-backed delivery queue with retry and backoff, dead-letter list and a primary/secondary provider failover; worker process. Decision at the start of N4: hand-written queue on Redis structures versus taskiq with its Redis broker (media M4 recommends taskiq); verify versions first.
- ⬜ N5 Live push (README §4.4): one-time stream tickets (short TTL, consumed on first use), SSE endpoint with Redis Pub/Sub fan-out, heartbeat every 15 s, `Last-Event-ID` replay from the inbox, at most 3 connections per user; then the WebSocket variant. Needs a design choice between `sse-starlette` and `StreamingResponse`; verify current versions first.
- ⬜ N6 Weekly digest (README §9): scheduler behind a Redis `lock:{job}` so one instance runs, per-user aggregation, templates; the catalog REST client and the account gRPC client (user email and locale) stay fakes until C5 and account Slice 7.
- ⬜ N7 Kafka consumers (README §5.6, §9): consume the account, catalog and media events, retry topics, DLQ, retryable versus non-retryable error classification, idempotent handling via the N3 dedupe. Deferred until account step 6.1 (Kafka and Schema Registry) and the Avro schemas exist; Kafka is unverified in the sandbox.
- Cross-cutting items notification ports later from account's Slice 4 and 9-11: i18n (N3 starts it), correlation id and logging (account 4.2), rate limit, CORS, observability, management port, Dockerfile and CI. Close-out of Phase 4 lists what was duplicated.

Design notes: notification writes its test helpers once, cleanly, in its own `conftest.py` instead of copying account's duplicated fake-identity code (see account 3.8). The `/health/ready` 503 answer stays a health report (not problem+json) so health checkers can read it.

### Phases 5 - 6 (outline only; plan each in detail when reached)

| Phase | Deliverable | Python tool ideas (verify current state first) |
| --- | --- | --- |
| 5 gateway | Off-the-shelf (Envoy/Traefik) first, then hand-written; aggregated docs and health | Traefik or Envoy, then FastAPI/httpx |
| 6 finish | Complete e2e suite, dashboards, Avro v2 evolution, port a service to another language | Hurl, k6 or pytest |

## 7. Delivery protocol for every slice

1. Read the cited README sections; restate the slice goal in two lines and list files to change. If a slice edits files Claude has not seen (for example `main.py`, `settings.py`), ask the user to paste exactly those files first and write nothing against files Claude has not read.
2. Implement in small steps; explain new concepts and new code to the learner.
3. Verify in the sandbox: `ruff check`, `ruff format --check`, `pyright`, unit tests, integration tests on embedded Postgres (native MongoDB for catalog, native Redis for notification), `alembic check` and up/down (account, media), a live HTTP smoke test, and a check from a clean extraction of the zip. When the repo is not available, verify against a reduced mirror of the pasted files and say so. For tests that guard a rule (for example i18n key parity), break the input on purpose once to prove the test can fail.
4. Package changed files as `account-sliceN-<topic>.zip` / `catalog-sliceCN-<topic>.zip` / `notification-sliceN<k>-<topic>.zip` (paths relative to repo root, no `.env`, no `.venv`). Since the user edits `pyproject.toml`/`uv.lock` locally, new dependencies are given as `uv add ...` commands, not shipped in the zip; the first slice of a brand-new service is the exception and ships both (done for catalog C1 and notification N1). Files the user owns outside the service folder (the realm file, compose blocks, `infra/.env` lines, `justfile` recipes, init scripts) are delivered separately, with the paste-in steps in one `...-paste-in.md` (or in the reply when it is only a few recipes). The shared `contracts/i18n` bundles are the one exception that ships in the zip.
5. Give the user: apply steps, just recipes to paste, what was verified, what was not, design decisions, 2-3 exercises, and the next slice.
6. The user runs the commands and reports; Claude fixes problems before moving on.
7. Update `CHEATSHEET.md`, then update sections 4 and 8 of this plan.

## 8. Progress log (fill in)

| Date | Slice.step | Result | Notes |
| --- | --- | --- | --- |
| 2026-10-11 | -1, 0 | ✅ | Practice app and scaffold; user's infra works, Keycloak token via curl OK |
| 2026-10-13 | 1 | ✅ | 8 unit + 3 integration green on user's machine |
| 2026-10-16 | 2 | ✅ | 34 unit + 14 integration green on user's machine |
| 2026-10-16 | 3.1 - 3.4 | ✅ | JWT validation, `CurrentUser`, permissions and guards, protected users routes; green on user's machine |
| 2026-10-19 | 3.5 | ✅ | `/users/me` with ETag and If-Match; tested by Claude against real Postgres; green on user's machine |
| 2026-10-19 - 21 | 3.6, 3.7 | ✅ | Keycloak admin client, compensation, disable on delete, realm file updated (3.6: 162 unit + 70 integration green on user's machine); refresh/logout endpoints (3.7) |
| 2026-10-22 | media M1 | ✅ | Media skeleton, migration 0001, health; Claude verified with Postgres 16 and Python 3.14.6 in the sandbox; 22 unit + 10 integration green on user's machine. Phase 2 started before account 3.8 (deferred) |
| 2026-10-23 | catalog C1 | ✅ | Catalog skeleton, Mongo wallpaper create/get/list/patch with ETag, indexes command; plan for C1-C7 agreed (ports with local stand-ins). Claude verified with native MongoDB 8.3.7 (also with auth on): 67 unit + 16 integration, curl smoke test, clean-extract check. User confirmed all green on their machine. Phase 3 started before account 3.8 (deferred) and media M2 |
| 2026-10-23 | notification N1 | ✅ | Notification skeleton (app factory, typed settings, lazy Redis client, health live/ready, problem+json errors, just recipes); plan for N1-N7 agreed (ports with fakes, Kafka last, `POST /admin/notifications/test` as the event entry until then). Claude verified with a native Redis 8.8.3 built from source and Python 3.14.4: 39 unit + 4 integration, Ruff and Pyright strict clean, live smoke test (Redis up, stopped, back up), clean-extract check of the zip. User confirmed all green on their machine. Phase 4 started before account 3.8 (deferred), media M2 and catalog C2 |
| 2026-10-23 | account 4.1 | ✅ | i18n: `Accept-Language` negotiation, shared bundles `contracts/i18n/{en,de,es}.json` (29 keys), localized problem+json (title, validation detail, field messages, `Content-Language`), exceptions with `title_key` / `message_key`, `account-slice4-i18n.zip`. Claude verified in a reduced mirror (Python 3.12.3, FastAPI 0.159.1, pydantic 2.14.1; only the four files the user pasted plus a stub `ApiModel`): 27 new unit tests, Ruff and Pyright strict clean, parity tests proven to fail on a deliberately broken bundle. Not verified by Claude: the real repo, the existing tests, a live smoke test, Python 3.14.5. User confirmed all green on their machine. The user moved to Slice 4 before 3.8 (deferred) and will convert the remaining English exception `detail` strings himself; 4.2 is next (design agreed, files requested) |
|  |  |  |  |

## 9. Known gotchas and open items

- Postgres 18 volume path (section 4). Confirm the fix.
- Account step 3.8 is deferred, not dropped: the RSA-key/fake-JWKS test code will be duplicated in media M2, catalog C2 and notification N2. Revisit after M2 or right before C2.
- Media M4 enqueues after commit: a crash in between leaves an asset `PROCESSING` forever until the M6 requeue job exists.
- The sandbox ran Postgres 16 for media; the user's compose uses Postgres 18. Role/permission differences would only show up on the user's machine.
- Catalog tests ran on MongoDB **8.3.7** (native, sandbox) while the compose image is `mongo:8.0` (floating tag). The features used are stable across both, but a mismatch would only show on the user's machine. The exact current image tag was not confirmed by a search.
- Mongo init script and compose block could only be tested by the user (no Docker in the sandbox). The script runs once on an empty volume; if Mongo ever started before it existed, the user `catalog_svc` is missing: remove only the Mongo volume and start again. `just infra-reset` also works but wipes Postgres and Keycloak data too.
- Catalog `POST /wallpapers` has a **temporary** `authorId` field and every catalog route is public: both disappear in C2 (owner = token `sub`; public callers see only `PUBLISHED` by default). Until then the list shows every status.
- Catalog decisions that are ours, not the README's: the category list and the `REJECTED` status; `size` above 100 is clamped (not rejected); `null` in a PATCH body means 'not sent'; `DELETE` and `PUT` wait for C2.
- Catalog sorting by `title` uses MongoDB's default binary collation (uppercase before lowercase). A case-insensitive sort needs a collation on the query and index; decide in C3 when search takes over text ordering.
- Catalog offset paging uses `skip`/`limit` plus `count_documents`: fine for small pages, slower on deep pages. Keyset (cursor) pagination arrives in C3 (README §5.2).
- Catalog has no MongoDB schema validator and no migration tool: documents are validated in the application and indexes come from `just catalog-indexes`. Revisit if the document shape changes (C7 fills `variants`, `dimensions`, `palette`, `blurhash`).
- The catalog health endpoints live on the main port until the management-port slice (like account before step 7.4). The same holds for notification.
- Notification: every route is public (only health exists); authentication arrives in N2. The service refuses to start without `NOTIFICATION_REDIS_URL` (no default, on purpose), so a fresh checkout needs `.env` copied from `.env.example`.
- Notification ran in the sandbox against Redis **8.8.3** (native, built from source; same version as the compose tag) with Python **3.14.4** (the user has 3.14.5). The user's compose Redis was confirmed working through the user's own green integration run; whether it requires a password was not checked in the sandbox (no Docker).
- Notification's dev port **8083** is our choice (account 8080, catalog 8082, media 8090); change it in the `notification-run` recipe if it collides with something else.
- Notification's tests keep helpers in `conftest.py` fixtures because the test folders are not packages. If a later slice needs shared helper classes, either keep using fixtures or turn the test folders into packages for all services at once (not per service).
- Notification depends on pieces that are not built yet: Kafka and Schema Registry (account step 6.1), Avro schemas for the catalog and media events (only `account.user.registered.v1` exists), the account gRPC server (Slice 7) and the catalog REST client (C5). N3 - N6 use ports with fakes; N7 (Kafka) stays unverified in the sandbox even when built.
- Notification's integration-test cleanup uses `KEYS it:*`, which is fine on a dev Redis but must never appear in service code (use `SCAN`).
- Since Slice 3 the overlay zips no longer carry `pyproject.toml` or `uv.lock` for existing services: new dependencies arrive as `uv add ...` commands, and small edits to files the user owns (for example the Keycloak realm file) are delivered separately. If an older zip overwrote them, merge by hand. (The first catalog and notification slices shipped both because those services were new.)
- If the user did the optional 'add bio column' exercise before Slice 2, undo it first (`alembic downgrade -1`, delete that migration), because migration 0002 adds `bio`.
- Soft-deleted users keep their username and email reserved until the purge job (6.5) exists; a test pins this rule.
- **Account i18n (4.1) leftovers:** (a) hard-coded English `detail` strings in domain and security code still come out in English in every language; the user converts them himself (`rg -n "Exception\(" src`, then give each a `message_key` and add the keys to all three bundles); (b) the English wording of validation messages changed in 4.1 to the README style (for example `username must be at least 3 characters long.`), and pydantic's text is still used for validator types without a key (custom validators, any new pydantic error type) until they get keys; (c) framework 404/405 titles and details are localized, a route's own message is not; (d) a new `AppException` subclass that forgets `title_key` shows its parent's title; (e) `FieldIssue` now has a dict-valued field, so do not put instances in sets or use them as dict keys; (f) the bundle folder comes from `ACCOUNT_I18N_DIR` or is found by walking up to `contracts/i18n`: the Docker image (11.1) must bundle the files and set the variable; (g) `Vary: Accept-Language` is not sent.
- Account step 4.1 was verified by Claude only in a reduced mirror (Python 3.12, only the pasted files plus a stub `ApiModel`), not against the real repo or on Python 3.14.5; the user's own green run is the real confirmation. Media, catalog and notification still return English-only messages (notification: until N3); `traceId` is missing from errors until step 9.3.
- Realm secrets, demo passwords and the `dev-tools` password-grant client are dev-only; never reuse them outside a local machine.
- Keycloak runs in `start-dev` mode; production mode is step 11.7.
- Keycloak imports the realm only on first start. Whenever `infra/keycloak/realm-export.json` changes, recreate Keycloak's data to apply it. The live-Keycloak integration tests fail with a clear message if the realm is outdated.
- Ownership relies on `users.id` = Keycloak `sub`. That holds for users registered with `ACCOUNT_IDENTITY_PROVIDER=keycloak`; rows created with the `local` provider (random ids, no login) can never be owned by a real Keycloak login. Reset the dev database when switching. The same applies to catalog wallpapers whose author came from the `local` stand-in.
- Access tokens are stateless (lifetime 300 s): after an account is deleted or its Keycloak user disabled, an already-issued token keeps working until it expires. A disabled user cannot get new tokens (verified for password login in 3.6).
- Service-account tokens (client credentials) have no `aud` claim, and our validator requires `aud=account-svc`. Before other services call account-svc (gRPC, step 7.3; catalog C5; notification N6), add an audience mapper to their clients in the realm.
- Postgres reports only the FIRST violated unique constraint, so a registration that duplicates both username and email can report just one field in the race case. The normal path reports both.
- `httpx2` is imported as `httpx2`, and `httpx2.codes` is not an int enum: compare status codes with `http.HTTPStatus`.
- The Keycloak token issuer is the host URL (`http://localhost:8180/realms/wallpaperhub`); when services run inside Docker later, align the issuer settings (Keycloak hostname) so validation still matches.
