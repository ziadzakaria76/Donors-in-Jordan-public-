"""Database connection.

Postgres in every deployed environment; SQLite only for local runs and tests.
The URL comes from DATABASE_URL, which Replit sets for us — there is no
credential in this file and none will be added.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base

DEFAULT_URL = "sqlite:///./gulftrack.db"

_engine: Engine | None = None
_Session: sessionmaker[Session] | None = None


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", DEFAULT_URL)
    # Replit and several hosts still hand out the legacy postgres:// scheme,
    # which SQLAlchemy 2 does not accept.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def get_engine() -> Engine:
    global _engine, _Session
    if _engine is None:
        url = database_url()
        kwargs: dict = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs = {"connect_args": {"check_same_thread": False}}
        _engine = create_engine(url, **kwargs)
        _Session = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def init_db() -> None:
    """Create tables if absent.

    Adequate while the schema is settling. Before the first deployment that
    holds real data this is replaced by Alembic migrations — losing Fadi's
    application history to a schema change is not an acceptable failure.
    """
    Base.metadata.create_all(get_engine())


@contextmanager
def session_scope() -> Iterator[Session]:
    get_engine()
    assert _Session is not None
    session = _Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_scope() as session:
        yield session
