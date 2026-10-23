"""HTTP behavior of /api/v1/wallpapers with an in-memory store (no database)."""

from fastapi.testclient import TestClient

from tests.unit.conftest import InMemoryWallpaperStore, valid_body

URL = "/api/v1/wallpapers"


def create(client: TestClient, **overrides: object) -> dict[str, object]:
    response = client.post(URL, json=valid_body(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


# ---- create ----------------------------------------------------------------------------------


def test_create_returns_201_location_etag_and_pending_status(client: TestClient) -> None:
    response = client.post(URL, json=valid_body())
    assert response.status_code == 201
    body = response.json()
    assert response.headers["location"] == f"/api/v1/wallpapers/{body['id']}"
    assert response.headers["etag"] == '"1"'
    assert body["status"] == "PENDING_MEDIA"
    assert body["version"] == 1
    assert body["assetId"] == "ast_01HXABCDEFGH"
    assert body["favoriteCount"] == 0
    assert body["variants"] == []
    assert body["dimensions"] is None


def test_create_stores_an_author_snapshot(client: TestClient) -> None:
    body = create(client, authorId="abcdef123456")
    assert body["author"] == {
        "id": "abcdef123456",
        "username": "user-abcdef12",
        "displayName": "User abcdef12",
        "avatarUrl": None,
    }


def test_create_normalizes_tags(client: TestClient) -> None:
    body = create(client, tags=[" Forest ", "FOG", "forest"])
    assert body["tags"] == ["forest", "fog"]


def test_create_without_description_defaults_to_empty(client: TestClient) -> None:
    payload = valid_body()
    del payload["description"]
    response = client.post(URL, json=payload)
    assert response.status_code == 201
    assert response.json()["description"] == ""


def test_create_validation_errors_are_problem_json(client: TestClient) -> None:
    response = client.post(
        URL,
        json=valid_body(title="   ", tags=["ok", "bad tag!"], category="WEIRD", assetId="nope"),
    )
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["type"] == "https://wallpaperhub.dev/problems/validation-failed"
    assert problem["status"] == 400
    assert problem["instance"] == URL
    codes = {(e["field"], e["code"]) for e in problem["errors"]}
    assert ("title", "Size") in codes
    assert ("tags[1]", "Pattern") in codes
    assert ("category", "InvalidValue") in codes
    assert ("assetId", "Pattern") in codes


def test_create_reports_missing_fields_by_camel_case_name(client: TestClient) -> None:
    response = client.post(URL, json={})
    fields = {(e["field"], e["code"]) for e in response.json()["errors"]}
    assert {("title", "Required"), ("assetId", "Required"), ("authorId", "Required")} <= fields


def test_create_rejects_too_many_tags(client: TestClient) -> None:
    response = client.post(URL, json=valid_body(tags=[f"t{i}" for i in range(11)]))
    assert response.status_code == 400
    assert ("tags", "Size") in {(e["field"], e["code"]) for e in response.json()["errors"]}


def test_create_rejects_unknown_and_snake_case_fields(client: TestClient) -> None:
    payload = valid_body()
    payload["asset_id"] = "ast_01HXABCDEFGH"
    response = client.post(URL, json=payload)
    assert response.status_code == 400


def test_create_rejects_malformed_json(client: TestClient) -> None:
    response = client.post(URL, content="{not json", headers={"Content-Type": "application/json"})
    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "MalformedJson"


# ---- get -------------------------------------------------------------------------------------


def test_get_returns_wallpaper_with_etag(client: TestClient) -> None:
    created = create(client)
    response = client.get(f"{URL}/{created['id']}")
    assert response.status_code == 200
    assert response.headers["etag"] == '"1"'
    assert response.json() == created


def test_get_unknown_id_is_404_problem(client: TestClient) -> None:
    response = client.get(f"{URL}/wp_DOESNOTEXIST1")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == "https://wallpaperhub.dev/problems/not-found"


def test_get_malformed_id_is_400(client: TestClient) -> None:
    response = client.get(f"{URL}/not-an-id")
    assert response.status_code == 400
    assert response.json()["errors"][0] == {
        "field": "wallpaper_id",
        "code": "Pattern",
        "message": response.json()["errors"][0]["message"],
    }


def test_unknown_route_is_404_problem(client: TestClient) -> None:
    response = client.get("/api/v1/nothing-here")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")


# ---- list ------------------------------------------------------------------------------------


def seed(client: TestClient) -> None:
    create(client, title="Alpha", category="NATURE", tags=["forest"], authorId="u-alice")
    create(client, title="Bravo", category="CITY", tags=["night", "forest"], authorId="u-bob")
    create(client, title="Charlie", category="NATURE", tags=["fog"], authorId="u-alice")


def test_list_uses_the_paging_envelope_and_newest_first(client: TestClient) -> None:
    seed(client)
    body = client.get(URL).json()
    assert [w["title"] for w in body["items"]] == ["Charlie", "Bravo", "Alpha"]
    assert (body["page"], body["size"], body["totalItems"], body["totalPages"]) == (0, 20, 3, 1)


def test_list_pages(client: TestClient) -> None:
    seed(client)
    body = client.get(URL, params={"page": 1, "size": 2}).json()
    assert [w["title"] for w in body["items"]] == ["Alpha"]
    assert (body["page"], body["size"], body["totalItems"], body["totalPages"]) == (1, 2, 3, 2)


def test_list_page_past_the_end_is_empty_not_an_error(client: TestClient) -> None:
    seed(client)
    body = client.get(URL, params={"page": 9}).json()
    assert body["items"] == []
    assert body["totalItems"] == 3


def test_list_size_is_capped_at_100(client: TestClient) -> None:
    assert client.get(URL, params={"size": 5000}).json()["size"] == 100


def test_list_sorts_by_whitelisted_field(client: TestClient) -> None:
    seed(client)
    body = client.get(URL, params={"sort": "title,asc"}).json()
    assert [w["title"] for w in body["items"]] == ["Alpha", "Bravo", "Charlie"]


def test_list_rejects_unlisted_sort_field(client: TestClient) -> None:
    response = client.get(URL, params={"sort": "assetId,asc"})
    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "sort"


def test_list_rejects_bad_paging_numbers(client: TestClient) -> None:
    response = client.get(URL, params={"page": -1, "size": 0})
    assert response.status_code == 400
    assert {e["field"] for e in response.json()["errors"]} == {"page", "size"}
    assert {e["code"] for e in response.json()["errors"]} == {"Range"}


def test_list_filters(client: TestClient) -> None:
    seed(client)

    def titles(**params: str) -> list[str]:
        return [w["title"] for w in client.get(URL, params=params).json()["items"]]

    assert titles(category="NATURE") == ["Charlie", "Alpha"]
    assert titles(tag="Forest") == ["Bravo", "Alpha"]
    assert titles(authorId="u-bob") == ["Bravo"]
    assert titles(status="PUBLISHED") == []
    assert titles(category="NATURE", tag="fog") == ["Charlie"]


def test_list_rejects_unknown_filter_value(client: TestClient) -> None:
    assert client.get(URL, params={"status": "DELETED"}).status_code == 400


# ---- patch -----------------------------------------------------------------------------------


def test_patch_changes_only_sent_fields_and_bumps_version(client: TestClient) -> None:
    created = create(client)
    response = client.patch(
        f"{URL}/{created['id']}", json={"title": "New title"}, headers={"If-Match": '"1"'}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "New title"
    assert body["description"] == created["description"]
    assert body["tags"] == created["tags"]
    assert body["version"] == 2
    assert response.headers["etag"] == '"2"'
    assert body["updatedAt"] > created["updatedAt"]
    assert body["createdAt"] == created["createdAt"]


def test_patch_can_clear_description_and_change_category_and_tags(client: TestClient) -> None:
    created = create(client)
    body = client.patch(
        f"{URL}/{created['id']}",
        json={"description": "", "category": "SPACE", "tags": ["Stars"]},
        headers={"If-Match": '"1"'},
    ).json()
    assert (body["description"], body["category"], body["tags"]) == ("", "SPACE", ["stars"])


def test_patch_without_if_match_is_428(client: TestClient) -> None:
    created = create(client)
    response = client.patch(f"{URL}/{created['id']}", json={"title": "x"})
    assert response.status_code == 428
    assert response.json()["type"].endswith("/precondition-required")


def test_patch_with_stale_etag_is_412(client: TestClient) -> None:
    created = create(client)
    url = f"{URL}/{created['id']}"
    assert (
        client.patch(url, json={"title": "first"}, headers={"If-Match": '"1"'}).status_code == 200
    )
    response = client.patch(url, json={"title": "second"}, headers={"If-Match": '"1"'})
    assert response.status_code == 412
    assert client.get(url).json()["title"] == "first"


def test_patch_with_weak_etag_is_412(client: TestClient) -> None:
    created = create(client)
    response = client.patch(
        f"{URL}/{created['id']}", json={"title": "x"}, headers={"If-Match": 'W/"1"'}
    )
    assert response.status_code == 412


def test_patch_with_malformed_if_match_is_400(client: TestClient) -> None:
    created = create(client)
    response = client.patch(
        f"{URL}/{created['id']}", json={"title": "x"}, headers={"If-Match": "1"}
    )
    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "If-Match"


def test_patch_star_matches_any_version(client: TestClient) -> None:
    created = create(client)
    url = f"{URL}/{created['id']}"
    client.patch(url, json={"title": "one"}, headers={"If-Match": '"1"'})
    response = client.patch(url, json={"title": "two"}, headers={"If-Match": "*"})
    assert response.status_code == 200
    assert response.json()["version"] == 3


def test_patch_body_validation_runs_before_the_if_match_check(client: TestClient) -> None:
    created = create(client)
    response = client.patch(f"{URL}/{created['id']}", json={"title": ""})
    assert response.status_code == 400


def test_patch_with_no_fields_is_400(client: TestClient) -> None:
    created = create(client)
    response = client.patch(f"{URL}/{created['id']}", json={}, headers={"If-Match": '"1"'})
    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "body"


def test_patch_cannot_touch_status_or_author(client: TestClient) -> None:
    created = create(client)
    response = client.patch(
        f"{URL}/{created['id']}", json={"status": "PUBLISHED"}, headers={"If-Match": '"1"'}
    )
    assert response.status_code == 400


def test_patch_unknown_id_is_404(client: TestClient) -> None:
    response = client.patch(
        f"{URL}/wp_DOESNOTEXIST1", json={"title": "x"}, headers={"If-Match": '"1"'}
    )
    assert response.status_code == 404


def test_patch_lost_race_is_412(client: TestClient, store: InMemoryWallpaperStore) -> None:
    """Someone saves between our read and our write: the atomic version filter says no match."""
    created = create(client)
    store.fail_next_update = True
    response = client.patch(
        f"{URL}/{created['id']}", json={"title": "x"}, headers={"If-Match": '"1"'}
    )
    assert response.status_code == 412


def test_unexpected_error_is_a_generic_500_problem(
    client: TestClient, store: InMemoryWallpaperStore
) -> None:
    async def boom(*_args: object, **_kwargs: object) -> None:
        msg = "database exploded: password=secret"
        raise RuntimeError(msg)

    store.get = boom  # pyright: ignore[reportAttributeAccessIssue]
    safe_client = TestClient(client.app, raise_server_exceptions=False)
    response = safe_client.get(f"{URL}/wp_ANYTHINGHERE1")
    assert response.status_code == 500
    assert "secret" not in response.text
    assert response.json()["type"].endswith("/internal-error")
