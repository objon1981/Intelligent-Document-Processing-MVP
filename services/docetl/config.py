import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    service_name: str = "docetl"
    version: str = "1.0.0"
    debug: bool = False
    
    # Database configuration
    database_url: str = "postgresql://postgres:password@postgres:5432/document_processing"
    
    # External service URLs
    file_organizer_url: str = "http://file-organizer:8005"
    ocr_service_url: str = "http://ocr-service:8006"
    
    # Processing configuration
    default_language: str = "eng"
    max_concurrent_jobs: int = 5
    job_timeout: int = 600  # seconds
    
    # Redis configuration (for future use)
    redis_url: str = "redis://redis:6379/0"
    
    # CORS configuration
    cors_origins: list = ["http://localhost:3000", "http://localhost:3001"]
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        case_sensitive = False

# Create singleton instance
settings = Settings()