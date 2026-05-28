import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Always use centralized config for DATABASE_URL to avoid stale env vars
from src.backend.core.config import DATABASE_URL
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./raman_studio.db"

# Build engine kwargs — SQLite doesn't support pool_size/max_overflow/pool_recycle
_pg = DATABASE_URL.startswith("postgresql")
_engine_kwargs = {"pool_pre_ping": True}
if _pg:
    _engine_kwargs.update({"pool_size": 5, "max_overflow": 10, "pool_recycle": 1800})
else:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency for FastAPI endpoints to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

