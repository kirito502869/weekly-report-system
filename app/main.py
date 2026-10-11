import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from app import models  # Register model metadata before creating tables.
from app.database import Base, create_sqlite_engine
from app.logging_config import configure_logging
from app.routers import reports, users, work_items

logger = logging.getLogger(__name__)


def create_app(database_url: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging()
        engine = create_sqlite_engine(database_url)
        app.state.engine = engine
        app.state.session_factory = sessionmaker(bind=engine)
        try:
            Base.metadata.create_all(engine)
            logger.info("Weekly report application started")
            yield
        finally:
            engine.dispose()
            logger.info("Weekly report database connections disposed")

    application = FastAPI(title="Weekly Report API", lifespan=lifespan)
    application.include_router(users.router)
    application.include_router(work_items.router)
    application.include_router(reports.router)
    return application


app = create_app()
