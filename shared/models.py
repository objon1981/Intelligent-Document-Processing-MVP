from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, Text, Boolean, ForeignKey
from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel, Field
import uuid

# ---------------------------------
# SQLAlchemy Declarative Base
# ---------------------------------
class Base(DeclarativeBase):
    pass

# ---------------------------------
# SQLAlchemy Models
# ---------------------------------

class FileRecord(Base):
    __tablename__ = "files"

    file_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    stored_filename: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    file_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    upload_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_accessed: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processing_status: Mapped[str] = mapped_column(String, default="pending")
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    processing_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    jobs: Mapped[List["JobModel"]] = relationship("JobModel", back_populates="file_record")


class JobModel(Base):
    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id: Mapped[str] = mapped_column(String, ForeignKey("files.file_id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="queued")
    language: Mapped[str] = mapped_column(String, default="eng")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    file_record: Mapped["FileRecord"] = relationship("FileRecord", back_populates="jobs")

# ---------------------------------
# Pydantic Models - Files
# ---------------------------------

class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    file_size: int
    upload_timestamp: str
    status: str
    message: str

class FileMetadata(BaseModel):
    file_id: str
    filename: str
    original_filename: str
    file_size: int
    file_hash: str
    mime_type: str
    upload_timestamp: str
    processing_status: str
    processing_started_at: Optional[str] = None
    processing_completed_at: Optional[str] = None
    error_message: Optional[str] = None
    file_metadata: Optional[dict] = None

class StatusUpdateRequest(BaseModel):
    status: str = Field(..., description="New status: processing, completed, failed")
    error_message: Optional[str] = Field(None, description="Error message if status is failed")

class FileListResponse(BaseModel):
    files: List[FileMetadata]
    total: int
    page: int
    per_page: int

# ---------------------------------
# Pydantic Models - OCR
# ---------------------------------

class OCRRequest(BaseModel):
    language: str = Field(default="eng", description="Language code for OCR")
    file_id: Optional[str] = Field(None, description="Optional file ID for tracking")
    confidence_threshold: Optional[float] = Field(30.0, description="Minimum confidence threshold")

class TextBlock(BaseModel):
    text: str
    confidence: float
    bbox: List[int]  # [x, y, width, height]
    page: int

class OCRResult(BaseModel):
    file_id: Optional[str]
    processing_time: float
    total_pages: int
    language: str
    overall_confidence: float
    text_blocks: List[TextBlock]
    full_text: str
    metadata: Dict
    timestamp: str

class HealthResponse(BaseModel):
    status: str
    tesseract_version: str
    supported_languages: List[str]

# ---------------------------------
# Pydantic Models - Jobs
# ---------------------------------

class JobMetadata(BaseModel):
    job_id: str
    file_id: str
    language: Optional[str] = "unknown"
    created_at: str
    status: str
    error_message: Optional[str] = None

    class Config:
        orm_mode = True

class JobSummary(BaseModel):
    job_id: str
    file_id: str
    status: str
    language: str
    created_at: str
    error_message: Optional[str] = None

class JobListResponse(BaseModel):
    jobs: List[JobSummary]
