# catalog-service cheatsheet (concept -> where to look)

| Concept | File | One-line idea |
| --- | --- | --- |
| App factory + lifespan | `src/catalog/main.py` | `create_app()` builds the app; the lifespan opens the Mongo client on start and closes it on stop |
| Settings, fail fast | `src/catalog/config/settings.py` | `CATALOG_*` env vars; `mongodb_uri` has no default, so a missing value stops startup |
| Secret values | same | `SecretStr` hides the password in logs and `repr()` |
| Layers | `api/http` -> `domain` -> `repository` | HTTP details never reach the domain; MongoDB never reaches the routes |
| Port (interface) | `domain/ports.py` | `WallpaperStore` and `AuthorDirectory` say WHAT the domain needs, not HOW |
| Stand-in adapter | `infra/local_author_directory.py` | a fake that lets catalog run alone until the real gRPC client exists (C5) |
| Adapter factory | `infra/author_directory_factory.py` | settings choose the implementation |
| Async MongoDB client | `repository/database.py` | `AsyncMongoClient` connects lazily, so the service starts even if Mongo is down |
| Document <-> object | `repository/documents.py` | explicit field-by-field translation; README 6.3 names (`assetId`, `favoriteCount`) |
| Atomic optimistic lock | `repository/wallpaper_repository.py` | `find_one_and_update` with `{"_id", "version"}` and `$inc`: check and write in one step |
| Stable paging | same | sort by the chosen field PLUS `_id`, otherwise equal values can repeat or vanish between pages |
| Offset paging | `api/http/pagination.py` | `page`, `size` (capped 100), whitelisted `sort`; skip/limit gets slower on deep pages |
| Indexes by command | `repository/indexes.py`, `cli.py` | `just catalog-indexes`; never at startup (like migrations) |
| ETag + If-Match | `api/http/etag.py` | strong tag `"<version>"`; 428 missing, 412 stale or weak, 400 malformed, `*` allowed |
| problem+json | `api/http/errors.py` | every error (even 404 and unexpected 500) has the same RFC 9457 shape |
| camelCase on the wire | `dto/base.py` | `ApiRequest` accepts only camelCase and rejects unknown fields |
| Tag normalization | `dto/wallpaper.py` | `BeforeValidator` trims and lowercases BEFORE the pattern check |
| Fake store for tests | `tests/unit/conftest.py` | `InMemoryWallpaperStore` has the same contract as Mongo, so unit tests need no database |
| Integration tests | `tests/integration/` | real MongoDB, database `catalog_test`, collection dropped around every test |
