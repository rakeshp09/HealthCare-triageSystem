"""Backend Application Configuration Loader.

Loads settings from environment variables or .env file with production-ready fallbacks.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    """Application settings schema and loader."""
    PROJECT_NAME: str = "Multimodal Healthcare Triage & Handoff Platform"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api"
    
    # Security
    SECRET_KEY: str = "clinical-triage-ai-secret-key-2026-production"
    JWT_SECRET_KEY: str = "clinical-triage-jwt-super-secret-key-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # Database (PostgreSQL default)
    DATA_DIR: Path = BASE_DIR / "data"
    DATABASE_PATH: Path = BASE_DIR / "data" / "healthcare.db"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/healthcare_db"
    
    # File Storage
    UPLOAD_FOLDER: Path = BASE_DIR / "uploads"
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024  # 16 MB max
    
    # RAG Vector Store
    CHROMADB_DIR: Path = BASE_DIR / "data" / "chroma_db"
    
    # External AI APIs (Google Gen AI - Gemini)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    
    # Clinical Infrastructure
    FACILITY_NAME: str = "Community Health Center & Triage Unit"
    INFORMATICS_COMMAND: str = "District Health Informatics Command"
    
    # Multilingual
    SUPPORTED_LANGUAGES: list[str] = ["en", "hi", "or"]
    
    model_config = SettingsConfigDict(
        env_file=(
            str(BACKEND_DIR / ".env"),
            str(BASE_DIR / ".env"),
            str(BASE_DIR / ".env.local")
        ),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure directories exist
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(settings.CHROMADB_DIR, exist_ok=True)
