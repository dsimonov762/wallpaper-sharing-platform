"""Every error answer must be application/problem+json with the documented fields."""

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from notification.domain.exceptions import (
    AppException,
    ConflictException,
    FieldViolation,
    ForbiddenException,
    NotFoundException,
    ServiceUnavailableException,
    UnauthorizedException,
    ValidationException,
)

PROBLEM_TYPE_BASE = "https://wallpaperhub.dev/problems/"

probe = APIRouter(prefix="/_probe")


class Item(BaseModel):
    title: str = Field(min_length=3, max_length=10)
    count: int = Field(ge=1)
    slug: str = Field(pattern=r"^[a-z]+$")


@probe.get("/raise/{kind}")
async def raise_error(kind: str) -> None:
    errors: dict[str, AppException] = {
        "validation": ValidationException(
            errors=[FieldViolation("title", "Required", "Title is required.")]
        ),
        "unauthorized": UnauthorizedException(headers={"WWW-Authenticate": "Bearer"}),
        "forbidden": ForbiddenException(),
        "not-found": NotFoundException("Notification 42 does not exist."),
        "conflict": ConflictException(),
        "unavailable": ServiceUnavailableException("Redis is down."),
    }
    if kind == "boom":
        raise RuntimeError("secret internal detail")
    raise errors[kind]


@probe.post("/items")
async def create_item(item: Item) -> Item:
    return item


@probe.get("/page")
async def read_page(page: int = 0) -> int:
    return page


@pytest.fixture
def probe_client(app: FastAPI) -> TestClient:
    app.include_router(probe)
    return TestClient(app, raise_server_exceptions=False)


def assert_problem(response_text: str, content_type: str) -> None:
    assert content_type.startswith("application/problem+json")
    assert "secret internal detail" not in response_text


@pytest.mark.parametrize(
    ("kind", "status", "slug", "title"),
    [
        ("validation", 400, "validation-failed", "Validation failed"),
        ("unauthorized", 401, "unauthorized", "Unauthorized"),
        ("forbidden", 403, "forbidden", "Forbidden"),
        ("not-found", 404, "not-found", "Resource not found"),
        ("conflict", 409, "conflict", "Conflict"),
        ("unavailable", 503, "service-unavailable", "Service unavailable"),
    ],
)
def test_app_exceptions_become_problem_json(
    probe_client: TestClient, kind: str, status: int, slug: str, title: str
) -> None:
    response = probe_client.get(f"/_probe/raise/{kind}")

    assert response.status_code == status
    assert_problem(response.text, response.headers["content-type"])
    body = response.json()
    assert body["type"] == f"{PROBLEM_TYPE_BASE}{slug}"
    assert body["title"] == title
    assert body["status"] == status
    assert body["instance"] == f"/_probe/raise/{kind}"


def test_detail_is_included_when_given(probe_client: TestClient) -> None:
    body = probe_client.get("/_probe/raise/not-found").json()

    assert body["detail"] == "Notification 42 does not exist."


def test_field_errors_are_listed(probe_client: TestClient) -> None:
    body = probe_client.get("/_probe/raise/validation").json()

    assert body["errors"] == [
        {"field": "title", "code": "Required", "message": "Title is required."}
    ]
    assert body["detail"] == "One or more fields are invalid."


def test_exception_headers_are_sent(probe_client: TestClient) -> None:
    response = probe_client.get("/_probe/raise/unauthorized")

    assert response.headers["www-authenticate"] == "Bearer"


def test_unexpected_error_is_generic_500(probe_client: TestClient) -> None:
    response = probe_client.get("/_probe/raise/boom")

    assert response.status_code == 500
    assert_problem(response.text, response.headers["content-type"])
    body = response.json()
    assert body["type"] == f"{PROBLEM_TYPE_BASE}internal-error"
    assert body["detail"] == "An unexpected error occurred."


def test_body_validation_is_400_with_field_codes(probe_client: TestClient) -> None:
    response = probe_client.post("/_probe/items", json={"title": "ab", "count": 0, "slug": "A1"})

    assert response.status_code == 400
    assert_problem(response.text, response.headers["content-type"])
    codes = {(e["field"], e["code"]) for e in response.json()["errors"]}
    assert codes == {("title", "Size"), ("count", "Range"), ("slug", "Pattern")}


def test_missing_field_is_required(probe_client: TestClient) -> None:
    response = probe_client.post("/_probe/items", json={})

    codes = {(e["field"], e["code"]) for e in response.json()["errors"]}
    assert codes == {("title", "Required"), ("count", "Required"), ("slug", "Required")}


def test_wrong_type_is_invalid_format(probe_client: TestClient) -> None:
    response = probe_client.get("/_probe/page", params={"page": "abc"})

    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "page"
    assert response.json()["errors"][0]["code"] == "InvalidFormat"


def test_malformed_json_is_reported_on_body(probe_client: TestClient) -> None:
    response = probe_client.post(
        "/_probe/items", content='{"title":', headers={"content-type": "application/json"}
    )

    assert response.status_code == 400
    assert response.json()["errors"] == [
        {
            "field": "body",
            "code": "MalformedJson",
            "message": response.json()["errors"][0]["message"],
        }
    ]


def test_input_values_are_not_echoed(probe_client: TestClient) -> None:
    response = probe_client.post(
        "/_probe/items", json={"title": "x", "count": 1, "slug": "top-secret-value-123"}
    )

    assert "top-secret-value-123" not in response.text


def test_unknown_path_is_problem_json_404(client: TestClient) -> None:
    response = client.get("/nope")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["type"] == f"{PROBLEM_TYPE_BASE}not-found"
    assert body["title"] == "Not Found"
    assert "detail" not in body


def test_wrong_method_is_problem_json_405_with_allow_header(client: TestClient) -> None:
    response = client.post("/health/live")

    assert response.status_code == 405
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "GET" in response.headers["allow"]
