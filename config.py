"""Global Application Configuration.

Centralizes configuration settings across backend and frontend environments.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
# Load .env if present
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "backend" / ".env")

class Config:
    """Application configuration settings."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "clinical-triage-ai-secret-key-2026-production")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "clinical-triage-jwt-super-secret-key-2026")
    
    # Database Configuration
    DATA_DIR = BASE_DIR / "data"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATABASE_PATH = os.environ.get("DATABASE_PATH", str(DATA_DIR / "healthcare.db"))
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/healthcare_db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload folder for voice recordings and diagnostic reports
    UPLOAD_FOLDER = BASE_DIR / "uploads"
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    
    # ChromaDB Vector Store
    CHROMADB_DIR = BASE_DIR / "data" / "chroma_db"
    CHROMADB_DIR.mkdir(parents=True, exist_ok=True)
    
    # Session Settings
    SESSION_COOKIE_NAME = "triage_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours
    
    # Multilingual / i18n Settings
    BABEL_DEFAULT_LOCALE = "en"
    BABEL_SUPPORTED_LOCALES = ["en", "hi", "or"]
    
    # Clinical System Settings
    FACILITY_NAME = os.environ.get("FACILITY_NAME", "Community Health Center & Triage Unit")
    INFORMATICS_COMMAND = os.environ.get("INFORMATICS_COMMAND", "District Health Informatics Command")
    DEMO_MODE = False
