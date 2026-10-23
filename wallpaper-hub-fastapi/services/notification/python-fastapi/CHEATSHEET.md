# notification-service cheat sheet (concept -> file)

| Concept | File |
| --- | --- |
| App factory (`create_app`) and lifespan (startup/shutdown of shared objects) | `src/notification/main.py` |
| Typed settings, `NOTIFICATION_` prefix, fail fast, `SecretStr`, URL validator | `src/notification/config/settings.py` |
| Redis client (lazy connect, timeouts, `decode_responses`) | `src/notification/infra/redis_client.py` |
| Readiness probe with a time limit (`asyncio.timeout`) | `src/notification/infra/redis_client.py` (`ping_redis`) |
| Liveness vs readiness, 503 body | `src/notification/api/http/health.py` |
| Dependency injection from `app.state` (`RedisDep`, `SettingsDep`) | `src/notification/api/http/dependencies.py` |
| One place that builds problem+json answers | `src/notification/api/http/errors.py` |
| Validation errors as 400 with field codes (Required, Size, Pattern, Range, InvalidFormat, MalformedJson) | `src/notification/api/http/errors.py` |
| Exception model (`AppException` and subclasses) | `src/notification/domain/exceptions.py` |
| problem+json and health DTOs, camelCase base class | `src/notification/dto/` |
| Replace Redis in unit tests (`FakeRedis`, `dependency_overrides`) | `tests/unit/conftest.py` |
| Integration tests (marker, real Redis, `it:` test keys) | `tests/integration/`, `pyproject.toml` |
| Lint, type check, test configuration | `pyproject.toml` |
