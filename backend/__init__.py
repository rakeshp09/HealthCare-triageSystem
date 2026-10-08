"""Backend Package Initializer.

Exports the FastAPI application, database models, session engine, and clinical services.
"""

from .app.main import app
from .app.database import engine, SessionLocal, get_db, init_db, Base
from .app.models import (
    User,
    Case,
    Testimonial,
    ElectronicHealthRecord,
    SharedRecordLink,
    AuditLog
)
from .app.security import (
    get_current_user,
    hash_password,
    verify_password,
    create_access_token
)
from .services import (
    llm_service,
    embedding_service,
    speech_service,
    vision_service,
    extraction_service,
    language_service,
    rag_service,
    safety_service
)
from .rag.retriever import rag_retriever
from .rag.ingest import ingest_protocols

__all__ = [
    "app",
    "engine",
    "SessionLocal",
    "get_db",
    "init_db",
    "Base",
    "User",
    "Case",
    "Testimonial",
    "ElectronicHealthRecord",
    "SharedRecordLink",
    "AuditLog",
    "get_current_user",
    "hash_password",
    "verify_password",
    "create_access_token",
    "llm_service",
    "embedding_service",
    "speech_service",
    "vision_service",
    "extraction_service",
    "language_service",
    "rag_service",
    "safety_service",
    "rag_retriever",
    "ingest_protocols"
]
