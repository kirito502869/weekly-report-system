import pytest

from app.models import User


@pytest.fixture
def user(client):
    response = client.post("/users", json={"name": "Alice"})
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def item_payload():
    return {"title": "Build API", "description": "Implement CRUD",
            "category": "Engineering", "week_start": "2026-09-28"}


@pytest.fixture
def item(client, user, item_payload):
    response = client.post(f"/users/{user['id']}/work-items", json=item_payload)
    assert response.status_code == 201
    return response.json()


def test_create_user(client, db_session):
    response = client.post("/users", json={"name": " Alice "})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Alice"
    assert data["created_at"]
    assert db_session.get(User, data["id"]).name == "Alice"


@pytest.mark.parametrize("payload", [{}, {"name": " "}, {"name": None},
                                     {"name": "x" * 201}, {"name": "A", "id": 99}])
def test_invalid_user(client, payload):
    assert client.post("/users", json=payload).status_code == 422


def test_create_and_get_item(client, user, item, item_payload):
    assert item.items() >= item_payload.items()
    assert item["user_id"] == user["id"]
    assert item["status"] == "pending"
    assert item["created_at"] and item["updated_at"]
    response = client.get(f"/users/{user['id']}/work-items/{item['id']}")
    assert response.status_code == 200
    assert response.json() == item


@pytest.mark.parametrize("status", ["pending", "in_progress", "completed"])
def test_create_allowed_status(client, user, item_payload, status):
    response = client.post(f"/users/{user['id']}/work-items",
                           json=item_payload | {"status": status})
    assert response.status_code == 201
    assert response.json()["status"] == status


def test_empty_list(client, user):
    response = client.get(f"/users/{user['id']}/work-items")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("filters,indices", [
    ({}, [0, 1, 2, 3]),
    ({"week_start": "2026-09-28"}, [0, 1, 2]),
    ({"category": "Engineering"}, [0, 1, 3]),
    ({"status": "completed"}, [0, 2, 3]),
    ({"week_start": "2026-09-28", "category": "Engineering", "status": "completed"}, [0]),
    ({"category": "Unknown"}, []),
])
def test_list_filters(client, user, item_payload, filters, indices):
    url = f"/users/{user['id']}/work-items"
    changes = [{"status": "completed"}, {},
               {"category": "Planning", "status": "completed"},
               {"week_start": "2026-10-05", "status": "completed"}]
    items = []
    for change in changes:
        response = client.post(url, json=item_payload | change)
        assert response.status_code == 201
        items.append(response.json())
    response = client.get(url, params=filters)
    assert response.status_code == 200
    assert response.json() == [items[index] for index in indices]


def test_partial_update(client, user, item):
    url = f"/users/{user['id']}/work-items/{item['id']}"
    response = client.patch(url, json={"status": "completed", "description": ""})
    assert response.status_code == 200
    updated = response.json()
    assert updated["status"] == "completed"
    assert updated["description"] == ""
    for field in ("id", "user_id", "title", "category", "week_start", "created_at"):
        assert updated[field] == item[field]
    assert client.get(url).json() == updated


def test_update_all_editable_fields(client, user, item):
    url = f"/users/{user['id']}/work-items/{item['id']}"
    changes = {"title": " New title ", "description": "Details", "category": " Planning ",
               "status": "in_progress", "week_start": "2026-10-05"}
    response = client.patch(url, json=changes)
    assert response.status_code == 200
    assert response.json().items() >= (changes | {"title": "New title", "category": "Planning"}).items()
    assert client.get(url).json() == response.json()


def test_empty_patch_is_noop(client, user, item):
    response = client.patch(f"/users/{user['id']}/work-items/{item['id']}", json={})
    assert response.status_code == 200
    assert response.json() == item


def test_delete_item(client, user, item):
    url = f"/users/{user['id']}/work-items/{item['id']}"
    response = client.delete(url)
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(url).status_code == 404
    assert client.delete(url).status_code == 404
    assert client.get(f"/users/{user['id']}/work-items").json() == []


@pytest.mark.parametrize("method", ["post", "get"])
def test_missing_user_collection(client, item_payload, method):
    kwargs = {"json": item_payload} if method == "post" else {}
    response = client.request(method, "/users/999/work-items", **kwargs)
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
@pytest.mark.parametrize("missing_user", [False, True])
def test_missing_item(client, user, method, missing_user):
    user_id = 999 if missing_user else user["id"]
    kwargs = {"json": {"status": "completed"}} if method == "patch" else {}
    response = client.request(method, f"/users/{user_id}/work-items/999", **kwargs)
    assert response.status_code == 404
    assert response.json()["detail"] == "Work item not found"


def test_user_isolation(client, user, item, item_payload):
    other = client.post("/users", json={"name": "Bob"}).json()
    other_url = f"/users/{other['id']}/work-items"
    own = client.post(other_url, json=item_payload).json()
    assert client.get(other_url).json() == [own]
    assert client.get(other_url, params={"week_start": item["week_start"]}).json() == [own]
    foreign_url = f"{other_url}/{item['id']}"
    assert client.get(foreign_url).status_code == 404
    assert client.patch(foreign_url, json={"title": "Changed"}).status_code == 404
    assert client.delete(foreign_url).status_code == 404
    assert client.get(f"/users/{user['id']}/work-items/{item['id']}").json() == item


@pytest.mark.parametrize("change", [
    {"week_start": "2026-09-29"}, {"week_start": "bad-date"}, {"status": "done"},
    {"title": " "}, {"category": " "}, {"title": "x" * 201},
    {"category": "x" * 51}, {"user_id": 999}, {"id": 999},
    {"title": None}, {"description": None}, {"category": None},
    {"status": None}, {"week_start": None},
])
@pytest.mark.parametrize("method", ["post", "patch"])
def test_invalid_item_input(client, user, item, item_payload, change, method):
    collection_url = f"/users/{user['id']}/work-items"
    url = collection_url if method == "post" else f"{collection_url}/{item['id']}"
    payload = item_payload | change if method == "post" else change
    assert client.request(method, url, json=payload).status_code == 422
    assert client.get(collection_url).json() == [item]


@pytest.mark.parametrize("filters", [
    {"week_start": "2026-09-29"}, {"week_start": "bad-date"},
    {"status": "done"}, {"category": " "},
])
def test_invalid_filters(client, user, filters):
    assert client.get(f"/users/{user['id']}/work-items", params=filters).status_code == 422
