# media-service (Python / FastAPI) cheatsheet

Concept -> file. Paths are relative to `services/media/python-fastapi/`. Add a row for every new concept.

| Concept | Where |
| --- | --- |
| App factory, startup and shutdown (lifespan) | `src/media/main.py` |
| Typed settings, `MEDIA_*` variables, fail fast | `src/media/config/settings.py` |
| Database engine, session factory, readiness check | `src/media/repository/database.py` |
| Tables `media_asset` and `media_variant` | `src/media/repository/models.py` |
| Constraint naming convention | `NAMING_CONVENTION` in `src/media/repository/models.py` |
| Optimistic locking (`version` column) | `__mapper_args__` in `src/media/repository/models.py` |
| Allowed purposes and statuses (single source of truth) | `src/media/domain/models.py` |
| Domain exceptions (`AppException` family) | `src/media/domain/exceptions.py` |
| Errors as `application/problem+json` | `src/media/api/http/errors.py` |
| Health endpoints `/health/live`, `/health/ready` | `src/media/api/http/health.py` |
| Handing startup objects to routes (`Depends`) | `src/media/api/http/dependencies.py` |
| Where the `/api/v1` routes will be collected | `src/media/api/http/router.py` |
| Migrations (async Alembic, same settings as the app) | `migrations/env.py`, `migrations/versions/` |
| Unit tests without a database | `tests/unit/` (`conftest.py` sets a fake environment) |
| Integration tests with rollback after each test | `tests/integration/conftest.py` (`session` fixture) |
