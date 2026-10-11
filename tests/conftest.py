import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def engine(app, client):
    return app.state.engine


@pytest.fixture
def db_session(engine):
    with Session(engine) as session:
        yield session
        session.rollback()
