from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.app.core.config import get_settings


Base = declarative_base()


def create_database_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_recycle=3600,
        future=True,
    )


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def check_database() -> dict[str, Any]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"ok": True, "message": "MySQL connection ok"}
    except SQLAlchemyError as exc:
        return {"ok": False, "message": str(exc)}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
