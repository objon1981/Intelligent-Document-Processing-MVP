# app.py
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
import pytesseract
import logging
import io
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from config import Settings
from shared.models import OCRRequest, OCRResult, HealthResponse
from ocr_processor import OCRProcessor
from redis import Redis
from rq import Queue
from tasks import run_ocr_job
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="OCR Service",
    description="Advanced OCR service with multi-format support",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize settings and processor
settings = Settings()
processor = OCRProcessor(settings)

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check with Tesseract info"""
    try:
        tesseract_version = pytesseract.get_tesseract_version()
        return HealthResponse(
            status="healthy",
            tesseract_version=str(tesseract_version),
            supported_languages=pytesseract.get_languages(config='')
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthResponse(
            status="degraded",
            tesseract_version="unknown",
            supported_languages=[]
        )


@app.post("/extract", response_model=OCRResult)
async def extract_text(
    file: UploadFile = File(...),
    language: str = Form("eng"),
    file_id: str = Form(None),
    confidence_threshold: float = Form(30.0)
):
    """Extract text from uploaded file"""
    try:
        # Validate file size
        file_content = await file.read()
        if len(file_content) > settings.max_file_size:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large. Max size: {settings.max_file_size} bytes"
            )
        
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename required")
        
        allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png', 'tiff', 'tif', 'bmp']
        file_ext = file.filename.lower().split('.')[-1]
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Allowed: {allowed_extensions}"
            )
        
        # Process file
        result = await processor.process_file(
            file_content=file_content,
            filename=file.filename,
            language=language,
            file_id=file_id,
            confidence_threshold=confidence_threshold
        )
        
        logger.info(f"Successfully processed file: {file.filename}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR extraction failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8003, reload=True)

@app.get("/languages")
async def get_supported_languages():
    """Get list of supported languages"""
    return {
        "supported_languages": pytesseract.get_languages(config=''),
        "default": "eng"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "OCR Service",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "extract": "/extract",
            "languages": "/languages"
        }
    }


# Setup Redis and Queue
redis_conn = Redis(host="redis", port=6379, decode_responses=True)
task_queue = Queue(connection=redis_conn)

@app.post("/queue")
async def queue_file(
    file: UploadFile = File(...),
    language: str = Form("eng"),
    confidence_threshold: float = Form(30.0)
):
    """Queue file for background OCR processing"""
    try:
        file_content = await file.read()
        file_id = str(uuid.uuid4())

        job = task_queue.enqueue(
            run_ocr_job,
            file_content,
            file.filename,
            language,
            file_id,
            confidence_threshold
        )

        return {"job_id": job.id, "file_id": file_id, "status": "queued"}

    except Exception as e:
        logger.error(f"Failed to queue OCR job: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to queue job")

@app.get("/queue/{job_id}")
def get_queue_status(job_id: str):
    """Check status/result of queued job"""
    job = task_queue.fetch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job.id,
        "status": job.get_status(),
        "result": job.result if job.is_finished else None
    }
