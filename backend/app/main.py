"""FastAPI Application Entry Point.

Initializes FastAPI with CORS, static asset mount, routers, and protocol vector ingestion.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .auth import router as auth_router
from .cases import router as cases_router, approve_admission
from .analysis import router as analysis_router, extract_entities, upload_report
from .rag import router as rag_router
from .reports import router as reports_router
from .audit import router as audit_router
from ..rag.ingest import ingest_protocols

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for database table verification and protocol ingestion."""
    # Ensure database tables exist
    init_db()
    # Ingest clinical protocol guidelines into ChromaDB
    try:
        res = ingest_protocols()
        print(f"[FastAPI Startup] ChromaDB protocols indexed: {res.get('indexed_chunks', 0)} chunks.")
    except Exception as e:
        print(f"[FastAPI Startup] Notice on protocol ingestion: {e}")
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Multimodal AI-Assisted Clinical Triage, Protocol RAG, and Standardized Handoff API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Mount Uploads directory for static access to scans & voice recordings
if os.path.exists(settings.UPLOAD_FOLDER):
    app.mount("/static/uploads", StaticFiles(directory=str(settings.UPLOAD_FOLDER)), name="uploads")
    app.mount("/uploads", StaticFiles(directory=str(settings.UPLOAD_FOLDER)), name="uploads_alt")

# Register Routers
app.include_router(auth_router)
app.include_router(cases_router)
app.include_router(analysis_router)
app.include_router(rag_router)
app.include_router(reports_router)
app.include_router(audit_router)

# Route aliases without /api prefix for maximum client compatibility
app.add_api_route("/cases/{case_id}/approve-admission", approve_admission, methods=["POST"])
app.add_api_route("/cases/{case_id}/approve", approve_admission, methods=["POST"])
app.add_api_route("/extract_entities", extract_entities, methods=["POST", "GET"])
app.add_api_route("/api/extract_entities", extract_entities, methods=["POST", "GET"])
app.add_api_route("/upload_report", upload_report, methods=["POST"])
app.add_api_route("/api/upload_report", upload_report, methods=["POST"])
app.add_api_route("/upload-report", upload_report, methods=["POST"])
app.add_api_route("/api/upload-report", upload_report, methods=["POST"])

@app.get("/api/health", tags=["Health"])
def health_check():
    """System health and operational status probe."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "facility": settings.FACILITY_NAME
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
