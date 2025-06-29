from importlib import reload
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import logging
import io
import json

from config import Settings
from shared.database import Database
from shared.models import FileUploadResponse, FileMetadata, StatusUpdateRequest, FileListResponse
from file_manager import FileManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="File Organizer Service",
    description="File management service with PostgreSQL storage",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize settings, database, and file manager
settings = Settings()
db_instance = Database(settings.database_url)
file_manager = FileManager(
    settings.upload_dir, 
    settings.allowed_extensions, 
    settings.max_file_size
)

@app.on_event("startup")
async def startup_event():
    db_instance.create_tables()
    logger.info("Database tables created/verified")

def get_db():
    return next(db_instance.get_session())

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "file-organizer",
        "upload_dir": settings.upload_dir,
        "max_file_size": settings.max_file_size,
        "timestamp": "2025-06-24T21:00:00Z"
    }

@app.post("/process")
async def process_file_trigger(file_id: str = Query(...), db: Session = Depends(get_db)):
    try:
        await file_manager.trigger_processing(file_id, db)
        return {"message": "Processing started"}
    except Exception as e:
        logger.error(f"Failed to start processing: {str(e)}")
        raise HTTPException(status_code=500, detail="Processing failed")

@app.post("/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        file_content = await file.read()

        if not file.filename:
            raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

        file_record = await file_manager.save_file(file_content, file.filename, db)

        return FileUploadResponse(
            file_id=str(file_record.id),
            filename=str(file_record.original_filename),
            file_size=int(file_record.file_size.value), 
            upload_timestamp=file_record.upload_timestamp.isoformat(),
            status=str(file_record.processing_status),
            message="File uploaded successfully"
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Upload failed")

@app.get("/files/{file_id}", response_model=FileMetadata)
async def get_file_metadata(file_id: str, db: Session = Depends(get_db)):
    try:
        file_record = await file_manager.get_file(file_id, db)
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")

        return FileMetadata(
            file_id=str(file_record.id),
            filename=str(file_record.filename),
            original_filename=str(file_record.original_filename),
            file_size=int(file_record.file_size.value),
            file_hash=str(file_record.file_hash),
            mime_type=str(file_record.mime_type),
            upload_timestamp=file_record.upload_timestamp.isoformat(),
            processing_status=str(file_record.processing_status),
            processing_started_at=file_record.processing_started_at.isoformat() if getattr(file_record, "processing_started_at", None) else None,
            processing_completed_at=file_record.processing_completed_at.isoformat() if getattr(file_record, "processing_completed_at", None) else None,
            error_message=str(file_record.error_message) if file_record.error_message is not None else None,
            metadata=json.loads(file_record.file_metadata if isinstance(file_record.file_metadata, str) else "") if getattr(file_record, "file_metadata", None) is not None else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file metadata: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get file metadata")

@app.get("/files/{file_id}/download")
async def download_file(file_id: str, db: Session = Depends(get_db)):
    try:
        file_record = await file_manager.get_file(file_id, db)
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")

        file_content = await file_manager.get_file_content(file_record)

        return StreamingResponse(
            io.BytesIO(file_content),
            media_type=str(file_record.mime_type),
            headers={"Content-Disposition": f"attachment; filename={file_record.original_filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Download failed")

@app.put("/files/{file_id}/status")
async def update_file_status(file_id: str, status_update: StatusUpdateRequest, db: Session = Depends(get_db)):
    try:
        await file_manager.update_file_status(
            file_id, 
            status_update.status, 
            db, 
            status_update.error_message
        )

        return {"message": "Status updated successfully"}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Status update failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Status update failed")

@app.get("/files", response_model=FileListResponse)
async def list_files(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status: str = Query(None),
    db: Session = Depends(get_db)
):
    try:
        files, total = await file_manager.list_files(db, page, per_page, status)

        file_metadata_list = []
        for file_record in files:
            file_metadata_list.append(FileMetadata(
                file_id=str(file_record.id),
                filename=str(file_record.filename),
                original_filename=str(file_record.original_filename),
                file_size=file_record.file_size,
                file_hash=str(file_record.file_hash),
                mime_type=str(file_record.mime_type),
                upload_timestamp=file_record.upload_timestamp.isoformat(),
                processing_status=str(file_record.processing_status),
                processing_started_at=file_record.processing_started_at.isoformat() if file_record.processing_started_at else None,
                processing_completed_at=file_record.processing_completed_at.isoformat() if file_record.processing_completed_at else None,
                error_message=str(file_record.error_message) if file_record.error_message else None,
                metadata=json.loads(file_record.file_metadata) if file_record.file_metadata else None
            ))

        return FileListResponse(
            files=file_metadata_list,
            total=total,
            page=page,
            per_page=per_page
        )

    except Exception as e:
        logger.error(f"Failed to list files: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list files")

@app.delete("/files/{file_id}")
async def delete_file(file_id: str, db: Session = Depends(get_db)):
    try:
        await file_manager.delete_file(file_id, db)
        return {"message": "File deleted successfully"}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Delete failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Delete failed")

@app.get("/")
async def root():
    return {
        "service": "File Organizer Service",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "upload": "/upload",
            "process": "/process",
            "files": "/files",
            "file_metadata": "/files/{file_id}",
            "download": "/files/{file_id}/download",
            "update_status": "/files/{file_id}/status"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8005, reload=True)  # type: ignore
