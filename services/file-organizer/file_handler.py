import os
import hashlib
import magic
import uuid
import aiofiles
from pathlib import Path
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
import logging

# ✅ Import the shared model
from shared.models import FileRecord  # Assuming shared/ is on PYTHONPATH

logger = logging.getLogger(__name__)

class FileHandler:
    def __init__(self, upload_dir: str = "/app/uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
    async def save_file(self, content: bytes, original_filename: str, db: Session) -> FileRecord:
        """Save uploaded file and create database record"""
        file_id = str(uuid.uuid4())
        file_extension = Path(original_filename).suffix
        stored_filename = f"{file_id}{file_extension}"
        file_path = self.upload_dir / stored_filename

        file_hash = hashlib.sha256(content).hexdigest()

        # Check for duplicates
        existing_file = db.query(FileRecord).filter(
            FileRecord.file_hash == file_hash
        ).first()

        if existing_file:
            logger.info(f"Duplicate file detected: {original_filename}")
            from datetime import datetime
            # Only set last_accessed if it's an instance attribute, not the Column itself
            if hasattr(existing_file, "last_accessed") and not isinstance(getattr(type(existing_file), "last_accessed", None), property):
                setattr(existing_file, "last_accessed", datetime.utcnow())
            db.commit()
            return existing_file

        mime_type = magic.from_buffer(content, mime=True)

        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)

        file_record = FileRecord(
            file_id=file_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=str(file_path),
            mime_type=mime_type,
            file_size=len(content),
            file_hash=file_hash
        )

        db.add(file_record)
        db.commit()
        db.refresh(file_record)

        logger.info(f"Saved file: {original_filename} as {stored_filename}")
        return file_record

    async def get_file_content(self, file_id: str, db: Session) -> Optional[bytes]:
        """Get file content by file ID"""
        file_record = db.query(FileRecord).filter(
            FileRecord.file_id == file_id
        ).first()

        if not file_record:
            return None

        try:
            async with aiofiles.open(getattr(file_record, "file_path"), 'rb') as f:
                content = await f.read()

            from datetime import datetime
            setattr(file_record, "last_accessed", datetime.utcnow())
            db.commit()

            return content
        except FileNotFoundError:
            logger.error(f"File not found on disk: {file_record.file_path}")
            return None

    def get_file_metadata(self, file_id: str, db: Session) -> Optional[FileRecord]:
        """Get file metadata by file ID"""
        return db.query(FileRecord).filter(
            FileRecord.file_id == file_id
        ).first()

    def list_files(self, db: Session, page: int = 1, per_page: int = 50) -> tuple[List[FileRecord], int]:
        """List files with pagination"""
        offset = (page - 1) * per_page

        files = db.query(FileRecord).order_by(
            desc(FileRecord.upload_timestamp)
        ).offset(offset).limit(per_page).all()

        total = db.query(FileRecord).count()

        return files, total

    def update_processing_status(self, file_id: str, status: str, error_message: Optional[str], db: Session):
        """Update file processing status"""
        file_record = db.query(FileRecord).filter(
            FileRecord.file_id == file_id
        ).first()

        if file_record:
            setattr(file_record, "processing_status", status)
            setattr(file_record, "is_processed", (status == "completed"))
            if error_message:
                setattr(file_record, "error_message", error_message)
            db.commit()

    async def delete_file(self, file_id: str, db: Session) -> bool:
        """Delete file and its record"""
        file_record = db.query(FileRecord).filter(
            FileRecord.file_id == file_id
        ).first()

        if not file_record:
            return False

        try:
            os.unlink(getattr(file_record, "file_path"))
        except FileNotFoundError:
            logger.warning(f"Physical file not found: {file_record.file_path}")

        db.delete(file_record)
        db.commit()

        logger.info(f"Deleted file: {file_record.original_filename}")
        return True
