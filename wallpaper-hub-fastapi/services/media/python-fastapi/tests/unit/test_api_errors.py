from http import HTTPStatus
from typing import Annotated

from fastapi import FastAPI, Query
from fastapi.testclient import TestClient

from media.api.http.errors import PROBLEM_MEDIA_TYPE, register_exception_handlers
from media.domain.exceptions import (
    FieldIssue,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
    ValidationException,
)


def _client() -> TestClient:
    """A tiny app with routes that fail on purpose, wired with the real error handlers."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/not-found")
    async def not_found() -> None:
        raise NotFoundException("Asset 123 does not exist.")

    @app.get("/forbidden")
    async def forbidden() -> None:
        raise ForbiddenException

    @app.get("/unauthorized")
    async def unauthorized() -> None:
        raise UnauthorizedException(headers={"WWW-Authenticate": "Bearer"})

    @app.get("/invalid")
    async def invalid() -> None:
        raise ValidationException(
            errors=[FieldIssue("purpose", "InvalidValue", "Unknown purpose.")]
        )

    @app.get("/paged")
    async def paged(size: Annotated[int, Query(ge=1, le=100)] = 20) -> dict[str, int]:
        return {"size": size}

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("database password is hunter2")

    return TestClient(app, raise_server_exceptions=False)


def test_app_exception_becomes_problem_json() -> None:
    response = _client().get("/not-found")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE
    assert response.json() == {
        "type": "https://wallpaperhub.dev/problems/not-found",
        "title": "Not found",
        "status": 404,
        "detail": "Asset 123 does not exist.",
        "instance": "/not-found",
    }


def test_exception_without_detail_uses_its_title() -> None:
    body = _client().get("/forbidden").json()

    assert body["status"] == HTTPStatus.FORBIDDEN
    assert body["detail"] == "Forbidden"


def test_exception_can_carry_response_headers() -> None:
    response = _client().get("/unauthorized")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.headers["www-authenticate"] == "Bearer"


def test_field_issues_are_listed_in_errors() -> None:
    body = _client().get("/invalid").json()

    assert body["errors"] == [
        {"field": "purpose", "code": "InvalidValue", "message": "Unknown purpose."}
    ]


def test_request_validation_is_400_not_422() -> None:
    response = _client().get("/paged", params={"size": 500})

    body = response.json()
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert body["type"] == "https://wallpaperhub.dev/problems/validation-failed"
    assert body["errors"][0]["field"] == "size"
    assert body["errors"][0]["code"] == "Range"


def test_unknown_url_is_problem_json() -> None:
    response = _client().get("/nope")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE
    assert response.json()["type"] == "https://wallpaperhub.dev/problems/not-found"


def test_wrong_method_is_problem_json() -> None:
    response = _client().post("/paged")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert response.json()["title"] == "Method Not Allowed"


def test_unexpected_error_hides_internals() -> None:
    response = _client().get("/boom")

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "hunter2" not in response.text
    assert response.json()["detail"] == "An unexpected error occurred."
