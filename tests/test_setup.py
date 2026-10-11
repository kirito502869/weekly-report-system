from datetime import date

import pytest
from pydantic import ValidationError
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request

from app.database import get_db
from app.models import User, WorkItem, WorkItemStatus
from app.schemas import UserCreate, UserRead, WorkItemCreate, WorkItemRead, WorkItemUpdate


def test_application_startup(client, engine):
    assert set(client.get("/openapi.json").json()["paths"]) == {
        "/users", "/users/{user_id}/work-items",
        "/users/{user_id}/work-items/{item_id}",
        "/users/{user_id}/weekly-report",
    }
    assert set(inspect(engine).get_table_names()) == {"users", "work_items"}
    indexes = inspect(engine).get_indexes("work_items")
    assert any(index["column_names"] == ["user_id", "week_start"] for index in indexes)


def test_foreign_keys_enabled_on_each_connection(engine):
    with engine.connect() as first, engine.connect() as second:
        assert first.scalar(text("PRAGMA foreign_keys")) == 1
        assert second.scalar(text("PRAGMA foreign_keys")) == 1


def test_model_round_trip_and_defaults(db_session):
    user = User(name="Alice")
    item = WorkItem(user=user, title="Build API", category="Engineering",
                    week_start=date(2026, 9, 28))
    db_session.add(item)
    db_session.commit()
    item_id = item.id
    db_session.expire_all()
    stored = db_session.get(WorkItem, item_id)
    assert stored.user.name == "Alice"
    assert stored.user.work_items == [stored]
    assert stored.status == WorkItemStatus.pending
    assert stored.description == ""
    assert stored.created_at is not None
    assert stored.updated_at is not None
    assert UserRead.model_validate(stored.user).name == "Alice"
    assert WorkItemRead.model_validate(stored).week_start == date(2026, 9, 28)
    previous_update = stored.updated_at
    stored.status = WorkItemStatus.completed
    db_session.commit()
    db_session.refresh(stored)
    assert stored.status == WorkItemStatus.completed
    assert stored.updated_at >= previous_update


def test_orphan_item_rejected(db_session):
    db_session.add(WorkItem(user_id=999, title="Orphan", category="Test",
                            week_start=date(2026, 9, 28)))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    assert db_session.scalar(select(WorkItem)) is None


@pytest.mark.parametrize("status,week", [("invalid", "2026-09-28"), ("pending", "2026-09-29")])
def test_database_constraints(db_session, status, week):
    user = User(name="Alice")
    db_session.add(user)
    db_session.commit()
    with pytest.raises(IntegrityError):
        db_session.execute(text(
            "INSERT INTO work_items "
            "(user_id, title, description, category, status, week_start, created_at, updated_at) "
            "VALUES (:user_id, 'Task', '', 'Test', :status, :week, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ), {"user_id": user.id, "status": status, "week": week})
    db_session.rollback()


def test_session_dependency_rolls_back_and_propagates(app, client):
    request = Request({"type": "http", "app": app})
    dependency = get_db(request)
    session = next(dependency)
    session.add(User(name="Uncommitted"))
    session.flush()
    with pytest.raises(RuntimeError, match="request failed"):
        dependency.throw(RuntimeError("request failed"))
    with app.state.session_factory() as check:
        assert check.scalar(select(User)) is None


def test_session_dependency_does_not_auto_commit(app, client):
    dependency = get_db(Request({"type": "http", "app": app}))
    session = next(dependency)
    session.add(User(name="Uncommitted"))
    session.flush()
    with pytest.raises(StopIteration):
        next(dependency)
    with app.state.session_factory() as check:
        assert check.scalar(select(User)) is None


def test_create_schema_defaults_and_whitespace():
    assert UserCreate(name=" Alice ").name == "Alice"
    item = WorkItemCreate(title=" Task ", category=" Dev ", week_start="2026-09-28")
    assert item.title == "Task"
    assert item.category == "Dev"
    assert item.description == ""
    assert item.status == WorkItemStatus.pending


@pytest.mark.parametrize("changes", [
    {"title": " "}, {"title": "x" * 201}, {"category": " "},
    {"category": "x" * 51}, {"status": "done"},
    {"week_start": "2026-09-29"}, {"week_start": "not-a-date"},
    {"user_id": 1},
])
def test_invalid_create_schema(changes):
    payload = {"title": "Task", "category": "Dev", "week_start": "2026-09-28"}
    with pytest.raises(ValidationError):
        WorkItemCreate(**(payload | changes))


@pytest.mark.parametrize("status", list(WorkItemStatus))
def test_allowed_statuses(status):
    assert WorkItemCreate(title="Task", category="Dev", week_start="2026-09-28",
                          status=status.value).status == status


def test_partial_update():
    assert WorkItemUpdate().model_dump(exclude_unset=True) == {}
    assert WorkItemUpdate(title=" New ").model_dump(exclude_unset=True) == {"title": "New"}
    with pytest.raises(ValidationError):
        WorkItemUpdate(week_start="2026-09-29")


@pytest.mark.parametrize("field", ["title", "description", "category", "status", "week_start"])
def test_update_rejects_explicit_null(field):
    with pytest.raises(ValidationError):
        WorkItemUpdate(**{field: None})


@pytest.mark.parametrize("name", ["", "   ", "x" * 201])
def test_invalid_user_name(name):
    with pytest.raises(ValidationError):
        UserCreate(name=name)
