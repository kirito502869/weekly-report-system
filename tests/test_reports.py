import pytest


@pytest.fixture
def user(client):
    response = client.post("/users", json={"name": "Alice"})
    assert response.status_code == 201
    return response.json()


def create_item(client, user_id, **changes):
    payload = {"title": "Task", "category": "Engineering", "week_start": "2026-09-28"}
    response = client.post(f"/users/{user_id}/work-items", json=payload | changes)
    assert response.status_code == 201
    return response.json()


def get_report(client, user_id, week_start="2026-09-28"):
    response = client.get(f"/users/{user_id}/weekly-report", params={"week_start": week_start})
    assert response.status_code == 200
    return response.json()


def test_aggregation_multiple_categories_and_statuses(client, user):
    planning = create_item(client, user["id"], category="Planning", status="in_progress")
    completed = create_item(client, user["id"], status="completed")
    pending = create_item(client, user["id"])
    report = get_report(client, user["id"])
    assert report == {
        "user_id": user["id"], "user_name": "Alice",
        "week_start": "2026-09-28", "week_end": "2026-10-04",
        "total_items": 3, "completed_count": 1, "in_progress_count": 1, "pending_count": 1,
        "completion_percentage": 33.33,
        "items_by_category": {"Engineering": [completed, pending], "Planning": [planning]},
    }
    assert list(report["items_by_category"]) == ["Engineering", "Planning"]


def test_empty_week(client, user):
    assert get_report(client, user["id"]) == {
        "user_id": user["id"], "user_name": "Alice",
        "week_start": "2026-09-28", "week_end": "2026-10-04",
        "total_items": 0, "completed_count": 0, "in_progress_count": 0, "pending_count": 0,
        "completion_percentage": 0, "items_by_category": {},
    }


def test_week_and_user_isolation(client, user):
    other = client.post("/users", json={"name": "Bob"}).json()
    first = create_item(client, user["id"])
    second = create_item(client, user["id"], week_start="2026-10-05", status="completed")
    foreign = create_item(client, other["id"], status="in_progress")
    for user_id, week, expected in [
        (user["id"], "2026-09-28", first),
        (user["id"], "2026-10-05", second),
        (other["id"], "2026-09-28", foreign),
    ]:
        report = get_report(client, user_id, week)
        assert report["user_id"] == user_id
        assert report["total_items"] == 1
        assert report["items_by_category"] == {"Engineering": [expected]}
    assert get_report(client, user["id"], "2026-10-12")["total_items"] == 0


def test_missing_user(client):
    response = client.get("/users/999/weekly-report", params={"week_start": "2026-09-28"})
    assert response.status_code == 404
    assert response.json() == {"detail": "User not found"}


@pytest.mark.parametrize("params", [
    {}, {"week_start": "2026-09-29"}, {"week_start": "invalid"},
    {"week_start": "2026-02-30"}, {"week_start": ""}, {"week_start": "9999-12-27"},
])
def test_invalid_week(client, user, params):
    response = client.get(f"/users/{user['id']}/weekly-report", params=params)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "week_start"]


@pytest.mark.parametrize("completed,total,expected", [
    (0, 0, 0), (0, 2, 0), (2, 2, 100), (1, 2, 50), (1, 3, 33.33), (2, 3, 66.67),
])
def test_completion_percentage(client, user, completed, total, expected):
    for index in range(total):
        create_item(client, user["id"], status="completed" if index < completed else "pending")
    report = get_report(client, user["id"])
    assert report["total_items"] == total
    assert report["completed_count"] == completed
    assert report["pending_count"] == total - completed
    assert report["in_progress_count"] == 0
    assert report["completion_percentage"] == expected


def test_report_reflects_edits_without_mutating_items(client, user):
    item = create_item(client, user["id"])
    url = f"/users/{user['id']}/work-items/{item['id']}"
    initial = get_report(client, user["id"])
    assert get_report(client, user["id"]) == initial
    assert client.get(url).json() == item
    assert client.patch(url, json={"status": "completed"}).status_code == 200
    assert get_report(client, user["id"])["completion_percentage"] == 100
    assert client.delete(url).status_code == 204
    assert get_report(client, user["id"])["total_items"] == 0


def test_week_end_crosses_year(client, user):
    assert get_report(client, user["id"], "2025-12-29")["week_end"] == "2026-01-04"
