# db.py

from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, Text,
    ForeignKey
)
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from typing import Generator
import uuid

from config import settings

# ---------------------------------
# SQLAlchemy Base & Engine
# ---------------------------------

DATABASE_URL = settings.database_url

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Connection health checks
    pool_recycle=300,    # Recycle every 5 minutes
    echo=getattr(settings, "debug", False)  # SQL query logging in debug mode
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ---------------------------------
# SQLAlchemy Models
# ---------------------------------

class FileRecord(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_hash = Column(String(64), nullable=False, unique=True)
    mime_type = Column(String(100), nullable=False)
    upload_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    processing_status = Column(String(50), default="uploaded", nullable=False)
    processing_started_at = Column(DateTime, nullable=True)
    processing_completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    file_metadata = Column(Text, nullable=True)

    # One-to-many relationship with jobs
    jobs = relationship("JobModel", back_populates="file_record")


class JobModel(Base):
    __tablename__ = "jobs"

    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=False)
    status = Column(String(50), default="queued")
    language = Column(String(10), default="eng")
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    result = Column(Text, nullable=True)

    # Many-to-one relationship to file
    file_record = relationship("FileRecord", back_populates="jobs")

# ---------------------------------
# Database Utility
# ---------------------------------

class Database:
    def __init__(self, database_url: str = DATABASE_URL):
        self.engine = engine
        self.SessionLocal = SessionLocal

    def create_tables(self):
        """Create tables based on defined models."""
        try:
            Base.metadata.create_all(bind=self.engine)
            print("✅ Database tables created successfully.")
        except Exception as e:
            print(f"❌ Error creating tables: {e}")
            raise

    def get_session(self) -> Generator:
        """Yield a DB session for dependency injection."""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def get_db_session(self):
        """Return a direct session object."""
        return self.SessionLocal()

    def test_connection(self) -> bool:
        """Test DB connection."""
        try:
            with self.engine.connect() as conn:
                conn.execute("SELECT 1")  # type: ignore
            print("✅ Database connection successful.")
            return True
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False

# ---------------------------------
# FastAPI Dependency
# ---------------------------------

def get_db() -> Generator:
    """FastAPI-compatible DB session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
