# config.py
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    tesseract_cmd: str = "/usr/bin/tesseract"
    supported_languages: List[str] = [
        "eng", "fra", "deu", "spa", "ita", "por", "hau", "ibo", "yor"
    ]
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    temp_dir: str = "/tmp/ocr"
    confidence_threshold: float = 30.0
    
    class Config:
        env_file = ".env"
        
settings = Settings()        