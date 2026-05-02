"""
Database Configuration
======================
PostgreSQL database setup with SQLAlchemy ORM.

Author: VidyuthLabs
Date: May 1, 2026
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import logging

logger = logging.getLogger(__name__)

# Database URL from environment variable
# Format: postgresql://user:password@host:port/database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://raman:raman123@localhost:5432/raman_studio"
)

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=10,  # Connection pool size
    max_overflow=20,  # Max connections beyond pool_size
    echo=False  # Set to True for SQL query logging
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for all models (singleton pattern to avoid redefinition)
_base = None

def get_base():
    """Get or create the declarative base."""
    global _base
    if _base is None:
        _base = declarative_base()
    return _base

Base = get_base()


def get_db() -> Generator[Session, None, None]:
    """
    Get database session.
    
    Usage in FastAPI:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database.
    
    Creates all tables defined in models.
    """
    try:
        # Import all models to register them
        from vanl.backend.core import models  # noqa
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def drop_db():
    """
    Drop all tables.
    
    WARNING: This will delete ALL data!
    Only use in development/testing.
    """
    try:
        Base.metadata.drop_all(bind=engine)
        logger.warning("All database tables dropped")
    except Exception as e:
        logger.error(f"Failed to drop database: {e}")
        raise


# Redis configuration for caching and sessions
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

try:
    import redis
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    logger.info("Redis connection established")
except ImportError:
    logger.warning("Redis not installed - caching disabled")
    redis_client = None
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    redis_client = None


def get_redis():
    """Get Redis client."""
    return redis_client
