from __future__ import annotations

import os
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session


class DBBase(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def init_db(db_url: str | None = None):
    global _engine, _SessionLocal
    url = db_url or os.environ.get("DATABASE_URL", "sqlite:///data/simulations.db")
    if url.startswith("sqlite"):
        db_path = url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(url, echo=False)
    _SessionLocal = sessionmaker(bind=_engine)
    DBBase.metadata.create_all(_engine)
    _run_migrations(_engine)


def _run_migrations(engine) -> None:
    """Add columns introduced after initial schema creation."""
    with engine.connect() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(doctrine_entries)"))}
        if "name" not in cols:
            conn.execute(text("ALTER TABLE doctrine_entries ADD COLUMN name VARCHAR DEFAULT ''"))
            conn.commit()


def get_session() -> Session:
    if _SessionLocal is None:
        init_db()
    return _SessionLocal()