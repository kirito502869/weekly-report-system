"""SQLite engine and request-scoped sessions."""

import os
from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


def create_sqlite_engine(database_url: str | None = None) -> Engine:
    engine = create_engine(
        database_url or os.getenv("DATABASE_URL", "sqlite:///./weekly_report.db"),
        connect_args={"check_same_thread": False},
    )
    if engine.dialect.name != "sqlite":
        raise ValueError("Only SQLite databases are supported")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        # SQLite requires this on every connection, outside a transaction.
        has_autocommit = hasattr(connection, "autocommit")
        if has_autocommit:
            previous = connection.autocommit
            connection.autocommit = True
        try:
            cursor = connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()
        finally:
            if has_autocommit:
                connection.autocommit = previous

    return engine


def get_db(request: Request) -> Generator[Session, None, None]:
    with request.app.state.session_factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
