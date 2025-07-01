from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import logging
import uuid
import httpx

from processor import DocumentProcessor
from config import settings
from shared.database import get_db, SessionLocal
from shared.models import JobMetadata, JobListResponse, JobModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DocETL Service",
    description="Document processing orchestration service",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_settings():
    return settings

def get_processor(cfg=Depends(get_settings)):
    return DocumentProcessor(cfg)

# ---------------------------- Request/Response Models ----------------------------

class ProcessDocumentRequest(BaseModel):
    file_id: str = Field(..., description="File ID from file organizer")
    language: Optional[str] = Field("eng", description="OCR language")

class ProcessDocumentResponse(BaseModel):
    message: str
    file_id: str
    job_id: str
    status: str

class DocumentResult(BaseModel):
    file_id: str
    processing_timestamp: str
    file_metadata: dict
    ocr_result: dict
    status: str
    processing_time_seconds: float

# ---------------------------- Background Task Functions ----------------------------

async def process_document_background(file_id: str, language: str, job_id: str, settings_config):
    """Background task for document processing with proper database session management"""
    db = SessionLocal()
    try:
        processor = DocumentProcessor(settings_config)
        await processor.process_document(file_id, language, job_id, db)
        logger.info(f"Background processing completed for job_id={job_id}")
    except Exception as e:
        logger.error(f"Background processing failed for job_id={job_id}: {str(e)}")
        # Update job status to failed
        try:
            job = db.query(JobModel).filter(JobModel.job_id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update job status in DB: {str(db_error)}")
    finally:
        db.close()

# ---------------------------- Routes ----------------------------

@app.get("/health")
async def health_check():
    logger.info("Health check requested")
    return {
        "status": "healthy",
        "service": "docetl",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/process", response_model=ProcessDocumentResponse)
async def process_document(
    request: ProcessDocumentRequest,
    background_tasks: BackgroundTasks,
    processor: DocumentProcessor = Depends(get_processor),
    db: Session = Depends(get_db)
):
    try:
        job_id = str(uuid.uuid4())
        logger.info(f"Received process request for file_id={request.file_id} with job_id={job_id}")

        language = request.language or "eng"  # Ensure string value

        # Create job record
        job = JobModel(
            job_id=job_id,
            file_id=request.file_id,
            status="queued",
            language=language,
            created_at=datetime.utcnow()
        )
        db.add(job)
        db.commit()
        logger.info(f"Job {job_id} saved to database with status 'queued'")

        # Queue background task with proper session handling
        background_tasks.add_task(
            process_document_background,
            request.file_id,
            language,
            job_id,
            settings  # Pass settings to background task
        )

        return ProcessDocumentResponse(
            message="Document processing started",
            file_id=request.file_id,
            job_id=job_id,
            status="queued"
        )

    except Exception as e:
        logger.error(f"Failed to start processing for file_id={request.file_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process/sync", response_model=DocumentResult)
async def process_document_sync(
    request: ProcessDocumentRequest,
    processor: DocumentProcessor = Depends(get_processor),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Synchronous processing requested for file_id={request.file_id}")

        language = request.language or "eng"  # Ensure string value

        result = await processor.process_document(request.file_id, language, db=db)
        return DocumentResult(**result)

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error during sync processing: {e}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"External error: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Sync processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{file_id}")
async def get_status(
    file_id: str,
    processor: DocumentProcessor = Depends(get_processor)
):
    try:
        logger.info(f"Status check requested for file_id={file_id}")
        metadata = await processor._get_file_metadata(file_id)
        return {
            "file_id": file_id,
            "status": metadata.get("status", "unknown"),
            "upload_timestamp": metadata.get("upload_timestamp"),
            "error_message": metadata.get("error_message")
        }
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.warning(f"File not found for status check: file_id={file_id}")
            raise HTTPException(status_code=404, detail="File not found")
        logger.error(f"HTTP error during status check for file_id={file_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get file status")
    except Exception as e:
        logger.error(f"Status check failed for file_id={file_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    per_page: int = Query(10, ge=1, le=100),
    processor: DocumentProcessor = Depends(get_processor)
):
    try:
        logger.info(f"Listing up to {per_page} recent jobs")
        jobs_metadata = await processor.get_recent_jobs(per_page)
        return JobListResponse(jobs=jobs_metadata)
    except Exception as e:
        logger.error(f"Failed to list jobs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list jobs")

@app.get("/jobs/{job_id}", response_model=JobMetadata)
async def get_job(
    job_id: str = Path(..., description="Job ID"),
    db: Session = Depends(get_db)
):
    logger.info(f"Fetching job info for job_id={job_id}")
    job = db.query(JobModel).filter(JobModel.job_id == job_id).first()
    if not job:
        logger.warning(f"Job not found: job_id={job_id}")
        raise HTTPException(status_code=404, detail="Job not found")

    return JobMetadata.model_validate(job)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8002, reload=True)  # type: ignore