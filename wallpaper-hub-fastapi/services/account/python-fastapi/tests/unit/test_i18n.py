"""Localization: language negotiation, bundles (key parity) and translated error responses."""

from collections.abc import Iterator
from typing import Annotated, Any

import pytest
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from account.api.http.errors import register_exception_handlers
from account.domain.exceptions import (
    AppException,
    ConflictException,
    FieldIssue,
    NotFoundException,
    ValidationException,
)
from account.i18n import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    MessageBundles,
    get_bundles,
    resolve_locale,
)
from account.i18n.messages import find_bundle_dir

# ---------- language negotiation ----------


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, "en"),
        ("", "en"),
        ("de", "de"),
        ("DE", "de"),
        ("de-AT", "de"),
        ("es-MX,es;q=0.9", "es"),
        ("fr,de;q=0.8,en;q=0.5", "de"),  # fr unsupported: next best
        ("en;q=0.3,de;q=0.9", "de"),  # weights beat the written order
        ("de;q=0,en", "en"),  # q=0 means "not acceptable"
        ("fr,it", "en"),  # nothing supported: default
        ("*", "en"),
        ("de;q=oops,es", "es"),  # a broken weight is ignored, not a crash
        (",,de", "de"),
    ],
)
def test_resolve_locale(header: str | None, expected: str) -> None:
    assert resolve_locale(header) == expected


# ---------- bundles ----------


def test_every_language_has_exactly_the_keys_of_english() -> None:
    bundles = get_bundles()
    english = bundles.keys(DEFAULT_LOCALE)
    for locale in SUPPORTED_LOCALES:
        assert bundles.keys(locale) == english, f"{locale}.json differs from en.json"


def test_placeholders_match_between_languages() -> None:
    import json
    import re

    directory = find_bundle_dir()
    texts = {
        locale: json.loads((directory / f"{locale}.json").read_text(encoding="utf-8"))
        for locale in SUPPORTED_LOCALES
    }

    def names(text: str) -> set[str]:
        return set(re.findall(r"\{(\w+)\}", text))

    for key, english in texts["en"].items():
        for locale in ("de", "es"):
            assert names(texts[locale][key]) == names(english), f"{locale}: {key}"


def test_translate_fills_placeholders_and_falls_back() -> None:
    bundles = MessageBundles({"en": {"hi": "Hello {name}, {missing}"}, "de": {}})
    assert bundles.translate("hi", "en", {"name": "Ada"}) == "Hello Ada, {missing}"
    assert bundles.translate("hi", "de", {"name": "Ada"}) == "Hello Ada, {missing}"  # en fallback
    assert bundles.translate("no.such.key", "en") == "no.such.key"  # last resort: the key


# ---------- translated responses ----------


class _Body(BaseModel):
    username: str = Field(min_length=3, max_length=10)
    age: int = Field(ge=18)


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/body")
    async def body(payload: _Body) -> dict[str, Any]:
        return payload.model_dump()

    @app.get("/query")
    async def query(size: Annotated[int, Query(le=100)]) -> dict[str, int]:
        return {"size": size}

    @app.get("/missing")
    async def missing() -> None:
        raise NotFoundException("User 42 does not exist.")

    @app.get("/keyed")
    async def keyed() -> None:
        raise ValidationException(
            "Bad input.",
            errors=[
                FieldIssue(
                    "name",
                    "NotBlank",
                    "name must not be blank.",
                    message_key="validation.notBlank",
                    message_args={"field": "name"},
                )
            ],
        )

    @app.get("/conflict")
    async def conflict() -> None:
        raise ConflictException("Username is taken.", message_key="error.conflict.title")

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internals")

    @app.get("/unknown-subclass")
    async def unknown_subclass() -> None:
        raise AppException("plain")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _lang(code: str) -> dict[str, str]:
    return {"Accept-Language": code}


def test_validation_error_in_english_by_default(client: TestClient) -> None:
    response = client.post("/body", json={"username": "ab", "age": 20})
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["content-language"] == "en"
    problem = response.json()
    assert problem["title"] == "Validation failed"
    assert problem["detail"] == "One or more fields are invalid."
    assert problem["errors"] == [
        {
            "field": "username",
            "code": "Size",
            "message": "username must be at least 3 characters long.",
        }
    ]


def test_validation_error_in_german(client: TestClient) -> None:
    response = client.post("/body", json={"username": "ab", "age": 20}, headers=_lang("de-DE,de"))
    problem = response.json()
    assert response.headers["content-language"] == "de"
    assert problem["title"] == "Validierung fehlgeschlagen"
    assert problem["detail"] == "Ein oder mehrere Felder sind ungültig."
    assert problem["errors"][0]["message"] == "username muss mindestens 3 Zeichen lang sein."
    assert problem["errors"][0]["code"] == "Size"  # codes never change with the language


def test_validation_error_in_spanish_with_several_problems(client: TestClient) -> None:
    response = client.post("/body", json={"age": 5}, headers=_lang("es"))
    messages = {e["field"]: e["message"] for e in response.json()["errors"]}
    assert messages == {
        "username": "username es obligatorio.",
        "age": "age debe ser al menos 18.",
    }


def test_too_long_range_and_type_messages(client: TestClient) -> None:
    long_name = client.post("/body", json={"username": "x" * 11, "age": 20}, headers=_lang("de"))
    assert long_name.json()["errors"][0]["message"] == (
        "username darf höchstens 10 Zeichen lang sein."
    )
    too_big = client.get("/query?size=500", headers=_lang("es"))
    assert too_big.json()["errors"][0]["message"] == "size debe ser como máximo 100."
    wrong_type = client.get("/query?size=abc", headers=_lang("de"))
    assert wrong_type.json()["errors"][0]["message"] == "size hat den falschen Typ."


def test_malformed_json_is_localized(client: TestClient) -> None:
    response = client.post(
        "/body", content="{not json", headers={"Content-Type": "application/json", **_lang("de")}
    )
    error = response.json()["errors"][0]
    assert error["code"] == "MalformedJson"
    assert error["field"] == "body"
    assert error["message"] == "Der Anfragetext ist kein gültiges JSON."


def test_app_exception_title_is_localized_and_detail_is_kept_without_a_key(
    client: TestClient,
) -> None:
    response = client.get("/missing", headers=_lang("es"))
    problem = response.json()
    assert response.status_code == 404
    assert problem["title"] == "Recurso no encontrado"
    assert problem["detail"] == "User 42 does not exist."  # no key yet: English text stays


def test_issue_with_a_key_is_translated(client: TestClient) -> None:
    response = client.get("/keyed", headers=_lang("de"))
    assert response.json()["errors"] == [
        {"field": "name", "code": "NotBlank", "message": "name darf nicht leer sein."}
    ]


def test_exception_message_key_translates_detail(client: TestClient) -> None:
    response = client.get("/conflict", headers=_lang("de"))
    assert response.json()["detail"] == "Konflikt"


def test_framework_404_and_405(client: TestClient) -> None:
    not_found = client.get("/nowhere", headers=_lang("de"))
    assert not_found.status_code == 404
    assert not_found.json()["title"] == "Ressource nicht gefunden"
    assert not_found.json()["detail"] == "Die angeforderte Ressource existiert nicht."
    wrong_method = client.delete("/body", headers=_lang("es"))
    assert wrong_method.status_code == 405
    assert wrong_method.json()["title"] == "Método no permitido"


def test_unexpected_error_is_localized_and_leaks_nothing(client: TestClient) -> None:
    response = client.get("/boom", headers=_lang("de"))
    problem = response.json()
    assert response.status_code == 500
    assert problem["title"] == "Interner Fehler"
    assert problem["detail"] == "Ein unerwarteter Fehler ist aufgetreten."
    assert "secret" not in response.text


def test_base_exception_still_has_a_title(client: TestClient) -> None:
    assert client.get("/unknown-subclass", headers=_lang("es")).json()["title"] == "Error interno"
