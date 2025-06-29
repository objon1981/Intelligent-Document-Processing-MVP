from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql://postgres-docker:password@localhost:5432/document_processing"
    upload_dir: str = "/app/uploads"
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    allowed_extensions: list = [
        "pdf", "jpg", "jpeg", "png", "tiff", "tif", "bmp"
    ]
    
    class Config:
        env_file = ".env"

settings = Settings()