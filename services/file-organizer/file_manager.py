import os
import hashlib
import uuid
import magic  # type: ignore
import shutil
import json
import aiofiles  # type: ignore
import fitz  # PyMuPDF
from pathlib import Path
from sqlalchemy.orm import Session
from shared.database import FileRecord
from typing import Optional, List
import logging
from datetime import datetime

logger = logging.getLogger("file_manager")

class FileManager:
    def __init__(self, upload_dir: str, allowed_extensions: List[str], max_file_size: int):
        self.upload_dir = Path(upload_dir)
        self.allowed_extensions = allowed_extensions
        self.max_file_size = max_file_size
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_file(self, file_content: bytes, original_filename: str, db: Session) -> FileRecord:
        try:
            await self._validate_file(file_content, original_filename)
            file_hash = hashlib.sha256(file_content).hexdigest()

            existing_file = db.query(FileRecord).filter(FileRecord.file_hash == file_hash).first()
            if existing_file:
                logger.info(f"Duplicate file detected: {file_hash}")
                return existing_file

            file_extension = original_filename.lower().split('.')[-1]
            unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
            file_path = self.upload_dir / unique_filename
            mime_type = magic.from_buffer(file_content, mime=True)

            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_content)

            metadata_dict = {
                "original_filename": original_filename,
                "mime_type": mime_type,
                "extension": file_extension,
                "size_bytes": len(file_content)
            }

            if mime_type == "application/pdf":
                try:
                    doc = fitz.open(stream=file_content, filetype="pdf")
                    metadata_dict["pdf_page_count"] = doc.page_count
                    pdf_meta = doc.metadata or {}

                    metadata_dict.update({
                        "pdf_title": pdf_meta.get("title"),
                        "pdf_author": pdf_meta.get("author"),
                        "pdf_subject": pdf_meta.get("subject"),
                        "pdf_keywords": pdf_meta.get("keywords"),
                        "pdf_creator": pdf_meta.get("creator"),
                        "pdf_producer": pdf_meta.get("producer")
                    })
                    doc.close()
                except Exception as e:
                    logger.warning(f"PDF metadata extraction failed: {e}")

            file_record = FileRecord(
                filename=unique_filename,
                original_filename=original_filename,
                file_path=str(file_path),
                file_size=len(file_content),
                file_hash=file_hash,
                mime_type=mime_type,
                upload_timestamp=datetime.utcnow(),
                processing_status="uploaded",
                file_metadata=json.dumps(metadata_dict)
            )

            db.add(file_record)
            db.commit()
            db.refresh(file_record)
            logger.info(f"File saved successfully: {unique_filename}")
            return file_record

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save file: {e}")
            raise

    async def get_file(self, file_id: str, db: Session) -> Optional[FileRecord]:
        try:
            return db.query(FileRecord).filter(FileRecord.id == file_id).first()
        except Exception as e:
            logger.error(f"Failed to retrieve file {file_id}: {e}")
            raise

    async def get_file_content(self, file_record: FileRecord) -> bytes:
        try:
            async with aiofiles.open(str(file_record.file_path), 'rb') as f:
                return await f.read()
        except Exception as e:
            logger.error(f"Failed to read file {file_record.id}: {e}")
            raise

    async def update_file_status(self, file_id: str, status: str, db: Session, error_message: Optional[str] = None):
        try:
            file_record = await self.get_file(file_id, db)
            if not file_record:
                raise ValueError("File not found")

            file_record.processing_status = FileRecord.ProcessingStatusEnum(status)  # If processing_status is a mapped string column, this is correct.
            # If processing_status is a SQLAlchemy Enum column, use:
            # file_record.processing_status = FileRecord.ProcessingStatusEnum(status)
            if status == "processing":
                setattr(file_record, "processing_started_at", datetime.utcnow())
            elif status in ["completed", "failed"]:
                setattr(file_record, "processing_completed_at", datetime.utcnow())

            if error_message:
                setattr(file_record, "error_message", error_message)

            db.commit()
            logger.info(f"Updated file {file_id} status to {status}")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update file status: {e}")
            raise

    async def list_files(self, db: Session, page: int = 1, per_page: int = 50, status: Optional[str] = None) -> tuple:
        try:
            query = db.query(FileRecord)
            if status:
                query = query.filter(FileRecord.processing_status == status)
            total = query.count()
            files = query.offset((page - 1) * per_page).limit(per_page).all()
            return files, total
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            raise

    async def delete_file(self, file_id: str, db: Session):
        try:
            file_record = await self.get_file(file_id, db)
            if not file_record:
                raise ValueError("File not found")

            if os.path.exists(str(file_record.file_path)):
                os.remove(str(file_record.file_path))

            db.delete(file_record)
            db.commit()
            logger.info(f"File deleted successfully: {file_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete file: {e}")
            raise

    async def _validate_file(self, file_content: bytes, filename: str):
        if len(file_content) > self.max_file_size:
            raise ValueError(f"File too large. Max size: {self.max_file_size} bytes")

        if not filename:
            raise ValueError("Filename is required")

        file_extension = filename.lower().split('.')[-1]
        if file_extension not in self.allowed_extensions:
            raise ValueError(f"File type not allowed. Allowed types: {self.allowed_extensions}")

    async def trigger_processing(self, file_id: str, db: Session):
        """Simulate or start a processing task on a file."""
        try:
            file_record = await self.get_file(file_id, db)
            if not file_record:
                raise ValueError("File not found")

            # Simulate starting a background task
            logger.info(f"Triggering processing for file {file_id}")
            # Use Enum if defined, otherwise assign string directly to .processing_status attribute
            if hasattr(FileRecord, "ProcessingStatusEnum"):
                file_record.processing_status = FileRecord.ProcessingStatusEnum.PROCESSING
            else:
                setattr(file_record, "processing_status", "processing")  # Assign using setattr to avoid type issues.
            setattr(file_record, "processing_started_at", datetime.utcnow())

            # Optional: Simulate completion
            setattr(file_record, "processing_completed_at", datetime.utcnow())
            if hasattr(FileRecord, "ProcessingStatusEnum"):
                file_record.processing_status = FileRecord.ProcessingStatusEnum.COMPLETED
            else:
                file_record.processing_status = FileRecord.ProcessingStatusEnum.COMPLETED

            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to trigger processing for file {file_id}: {e}")
            raise
