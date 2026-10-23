"""Every failure must come back as RFC 9457 application/problem+json.

Most tests here are about the SHAPE of errors, not about logging in, so `app_client` treats
every request as coming from an admin. `anonymous_client` is the real thing, without that
shortcut. Token checks themselves are tested in test_auth_dependency.py and tests/unit/security/.
"""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from account.api.http.dependencies import get_current_user, get_user_service
from account.domain.exceptions import ConflictException, FieldIssue, NotFoundException
from account.main import create_app
from account.security.current_user import CurrentUser


class ExplodingService:
    """Stands in for UserService and fails in the ways we want to test."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def get(self, user_id: UUID) -> None:
        raise self._error


ADMIN = CurrentUser(
    id="admin-1", email=None, locale=None, roles=frozenset({"USER", "ADMIN"}), scope=frozenset()
)


@pytest.fixture
def app_client() -> Iterator[TestClient]:
    """The app with token checking replaced by "the caller is an admin"."""
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def anonymous_client() -> Iterator[TestClient]:
    """The app exactly as deployed: no shortcut, so protected routes demand a token."""
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        yield client


def use_service(client: TestClient, service: object) -> None:
    app = client.app
    app.dependency_overrides[get_user_service] = lambda: service  # type: ignore[attr-defined]


def test_validation_errors_list_every_bad_field(app_client: TestClient) -> None:
    response = app_client.post(
        "/api/v1/registrations",
        json={"username": "Bad Name!", "email": "not-an-email", "password": "short"},
    )

    body = response.json()
    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert body["type"] == "https://wallpaperhub.dev/problems/validation-failed"
    assert body["instance"] == "/api/v1/registrations"
    codes = {error["field"]: error["code"] for error in body["errors"]}
    assert codes == {"username": "Pattern", "email": "Email", "password": "Size"}
    password_error = next(e for e in body["errors"] if e["field"] == "password")
    assert password_error["message"] == "password must be at least 12 characters long."


def test_validation_error_never_echoes_the_password(app_client: TestClient) -> None:
    response = app_client.post(
        "/api/v1/registrations",
        json={"username": "alice", "email": "alice@example.com", "password": "short-pw"},
    )

    assert "short-pw" not in response.text


def test_missing_body_fields_are_reported_as_required(app_client: TestClient) -> None:
    response = app_client.post("/api/v1/registrations", json={})

    assert {e["code"] for e in response.json()["errors"]} == {"Required"}


def test_malformed_json_is_a_400_problem(app_client: TestClient) -> None:
    response = app_client.post(
        "/api/v1/registrations",
        content="{not json",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["errors"][0] == {
        "field": "body",
        "code": "MalformedJson",
        "message": response.json()["errors"][0]["message"],
    }


def test_page_size_is_capped_at_100(app_client: TestClient) -> None:
    response = app_client.get("/api/v1/users", params={"size": 101})

    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "size"


def test_negative_page_is_rejected_as_a_400_problem(app_client: TestClient) -> None:
    response = app_client.get("/api/v1/users", params={"page": -1})

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["errors"][0]["field"] == "page"


def test_bad_uuid_in_path_is_a_400_problem(app_client: TestClient) -> None:
    response = app_client.get("/api/v1/users/not-a-uuid")

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "InvalidFormat"


def test_not_found_domain_exception_becomes_404_problem(app_client: TestClient) -> None:
    use_service(app_client, ExplodingService(NotFoundException("User was not found.")))

    response = app_client.get(f"/api/v1/users/{uuid4()}")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == "User was not found."


def test_conflict_includes_field_level_error(app_client: TestClient) -> None:
    error = ConflictException("exists", [FieldIssue("username", "AlreadyExists", "taken")])
    use_service(app_client, ExplodingService(error))

    response = app_client.get(f"/api/v1/users/{uuid4()}")

    assert response.status_code == 409
    assert response.json()["errors"] == [
        {"field": "username", "code": "AlreadyExists", "message": "taken"}
    ]


def test_unknown_url_is_a_404_problem(app_client: TestClient) -> None:
    response = app_client.get("/api/v1/nothing-here")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"


def test_wrong_method_is_a_405_problem_with_allow_header(app_client: TestClient) -> None:
    response = app_client.put("/api/v1/registrations", json={})

    assert response.status_code == 405
    assert "POST" in response.headers["allow"]
    assert response.headers["content-type"] == "application/problem+json"


def test_unexpected_error_hides_internals(app_client: TestClient) -> None:
    use_service(app_client, ExplodingService(RuntimeError("secret database detail")))

    response = app_client.get(f"/api/v1/users/{uuid4()}")

    assert response.status_code == 500
    assert "secret database detail" not in response.text
    assert response.json()["detail"] == "An unexpected error occurred."


def test_protected_route_without_token_is_a_401_problem(anonymous_client: TestClient) -> None:
    response = anonymous_client.get(f"/api/v1/users/{uuid4()}")

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["type"] == "https://wallpaperhub.dev/problems/unauthorized"
