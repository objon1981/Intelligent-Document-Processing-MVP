import httpx
import logging
import json
from typing import Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from services.docetl.config import settings
from shared.models import JobMetadata, JobModel

logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self, settings):
        self.settings = settings
        self.file_organizer_url = settings.file_organizer_url
        self.ocr_service_url = settings.ocr_service_url
        logger.info("DocumentProcessor initialized.")

    async def process_document(
        self, 
        file_id: str, 
        language: str = "eng", 
        job_id: Optional[str] = None, 
        db: Optional[Session] = None
    ) -> Dict:
        """
        Process a document with proper database session handling
        """
        logger.info(f"[{job_id or 'N/A'}] Start processing document: {file_id} with language {language}")

        start_time = datetime.utcnow()

        try:
            # Get file metadata
            file_metadata = await self._get_file_metadata(file_id)
            logger.debug(f"[{job_id or 'N/A'}] Retrieved file metadata: {file_metadata}")

            # Update file status to processing
            await self._update_file_status(file_id, "processing")

            # Update job status if job_id and db session provided
            if job_id and db:
                self._update_job_status(job_id, "processing", db)

            logger.debug(f"[{job_id or 'N/A'}] Updated status to 'processing'")

            # Perform OCR
            ocr_result = await self._perform_ocr(file_id, language)
            logger.debug(f"[{job_id or 'N/A'}] OCR result received")

            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()

            # Build result
            result = {
                "file_id": file_id,
                "job_id": job_id,
                "processing_timestamp": datetime.utcnow().isoformat(),
                "file_metadata": file_metadata,
                "ocr_result": ocr_result,
                "status": "completed",
                "processing_time_seconds": processing_time
            }

            # Update job status first (more important)
            if job_id and db:
                self._update_job_status(job_id, "completed", db, result=result)

            # Then update file status
            await self._update_file_status(file_id, "completed")

            logger.info(f"[{job_id or 'N/A'}] Successfully processed document: {file_id}")
            return result

        except Exception as e:
            logger.error(f"[{job_id or 'N/A'}] Document processing failed for {file_id}: {str(e)}", exc_info=True)

            # Update statuses to failed
            try:
                await self._update_file_status(file_id, "failed", str(e))
            except Exception as file_error:
                logger.error(f"Failed to update file status: {str(file_error)}")

            if job_id and db:
                try:
                    self._update_job_status(job_id, "failed", db, error_message=str(e))
                except Exception as job_error:
                    logger.error(f"Failed to update job status: {str(job_error)}")

            raise

    async def _get_file_metadata(self, file_id: str) -> Dict:
        """Get file metadata from file organizer service"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.file_organizer_url}/files/{file_id}", 
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def _update_file_status(
        self, 
        file_id: str, 
        status: str, 
        error_message: Optional[str] = None
    ):
        """Update file status in file organizer service"""
        async with httpx.AsyncClient() as client:
            data = {"status": status}
            if error_message:
                data["error_message"] = error_message

            response = await client.put(
                f"{self.file_organizer_url}/files/{file_id}/status",
                params=data,
                timeout=30.0
            )
            response.raise_for_status()

    async def _perform_ocr(self, file_id: str, language: str) -> Dict:
        """Perform OCR on the document using OCR service"""
        async with httpx.AsyncClient() as client:
            # Download file from file organizer
            file_response = await client.get(
                f"{self.file_organizer_url}/files/{file_id}/download",
                timeout=60.0
            )
            file_response.raise_for_status()

            # Prepare file for OCR service
            files = {
                "file": ("document", file_response.content, file_response.headers.get("content-type"))
            }
            data = {
                "language": language,
                "file_id": file_id
            }

            # Send to OCR service
            ocr_response = await client.post(
                f"{self.ocr_service_url}/extract",
                files=files,
                data=data,
                timeout=300.0
            )
            ocr_response.raise_for_status()
            return ocr_response.json()

    def _calculate_processing_time(self, start_time: str, end_time: str) -> float:
        """Calculate processing time between two ISO timestamps"""
        try:
            start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            return (end - start).total_seconds()
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to calculate processing time: {str(e)}")
            return 0.0

    def _update_job_status(
        self, 
        job_id: str, 
        status: str, 
        db: Session,
        result: Optional[Dict] = None, 
        error_message: Optional[str] = None
    ):
        """
        Update job status in database using provided session
        """
        if job_id is None:
            logger.warning("Cannot update job status: job_id is None.")
            return

        try:
            job = db.query(JobModel).filter(JobModel.job_id == job_id).first()
            if not job:
                logger.warning(f"Job ID {job_id} not found in DB.")
                return

            job.status = status

            if status in ["completed", "failed"]:
                job.completed_at = datetime.utcnow()

            if result:
                job.result = json.dumps(result)

            if error_message:
                job.error_message = error_message

            db.commit()
            logger.info(f"Job {job_id} status updated to '{status}' in DB.")

        except Exception as e:
            logger.error(f"Failed to update job {job_id} in DB: {str(e)}")
            db.rollback()
            raise

    async def get_recent_jobs(self, per_page: int = 10):
        """Get recent jobs from file organizer service"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.file_organizer_url}/files",
                params={"per_page": per_page},
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

            jobs = []
            for file in data.get("files", []):
                metadata = file.get("metadata", {}) or {}
                jobs.append(JobMetadata(
                    job_id=str(file.get("file_id", "")),
                    file_id=file.get("file_id", ""),
                    language=metadata.get("language", "unknown"),
                    created_at=file.get("upload_timestamp", datetime.utcnow().isoformat()),
                    status=file.get("processing_status", "unknown"),
                    error_message=file.get("error_message")
                ))
            return jobs