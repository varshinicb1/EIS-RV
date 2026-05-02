import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Use centralized config if available, otherwise fallback
try:
    from src.backend.core.config import DATABASE_URL
except ImportError:
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://raman_admin:raman_secure_password@localhost:5432/raman_enterprise"
    )

# Create SQLAlchemy engine with connection pool health checks.
# pool_pre_ping ensures stale connections are recycled before use,
# preventing "connection closed" errors after DB restarts.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=1800,  # Recycle connections every 30 minutes
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency for FastAPI endpoints to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

