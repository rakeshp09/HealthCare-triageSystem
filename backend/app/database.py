"""Database Session and Connection Management.

Configured for PostgreSQL (pgAdmin) production database management with SQLAlchemy engine pool.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

# Configure SQLite / PostgreSQL engine
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db() -> Generator:
    """FastAPI dependency yielding database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Creates database tables if they do not exist."""
    from . import models  # Ensure models are registered on Base.metadata
    Base.metadata.create_all(bind=engine)
