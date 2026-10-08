# Healthcare Triage Assistant - Backend Architecture

## Overview
The backend is a high-performance, asynchronous REST API built with **FastAPI**, **SQLAlchemy ORM**, **ChromaDB Vector Store**, and **Pydantic v2**. It coordinates multimodal intake (speech audio transcription, diagnostic document OCR), deterministic clinical safety risk rules, protocol-grounded RAG reasoning, and standardized 15-section handoff dossier reporting.

---

## Directory Layout
```
backend/
├── .env                         # API keys (OpenAI, ChromaDB, DB URI, JWT secret)
├── requirements.txt             # Backend dependencies
│
└── app/
    ├── config.py                # Pydantic settings loader from .env
    ├── main.py                  # FastAPI app entry point & router mounting
    ├── database.py              # SQLAlchemy engine, sessionmaker, fallback handler
    ├── models.py                # ORM models (User, Case, Testimonial, EHR, SharedLink, AuditLog)
    ├── schemas.py               # Pydantic validation schemas
    ├── security.py              # PBKDF2/bcrypt hashing + JWT tokens + role security
    │
    ├── auth.py                  # Authentication routes (/api/auth/login, signup, me, logout)
    ├── cases.py                 # Case CRUD, triage queue, nurse approval, doctor review
    ├── analysis.py              # Multimodal AI intake (audio STT, vision OCR, clinical analysis)
    ├── rag.py                   # RAG protocol search, document upload, reindexing
    ├── reports.py               # 15-section handoff dossier & ReportLab PDF generation
    └── audit.py                 # Immutable audit logs & governance compliance
│
└── services/
    ├── llm_service.py           # GPT completions with robust clinical fallback
    ├── embedding_service.py     # Vector embeddings (SentenceTransformers / ChromaDB)
    ├── speech_service.py        # Whisper STT + multilingual disfluency cleaning
    ├── vision_service.py        # OCR via Tesseract / Vision models
    ├── extraction_service.py    # Structured clinical entity extraction
    ├── language_service.py      # Multilingual translation & Hindi/Devanagari normalization
    ├── rag_service.py           # RAG retrieval & evidence-based triage synthesis
    └── safety_service.py        # Deterministic clinical safety rules & priority tagging
│
└── rag/
    ├── chroma_client.py         # ChromaDB persistent client manager
    ├── ingest.py                # Protocol document chunking & vector indexing
    ├── retriever.py             # Vector similarity search over protocols & cases
    └── documents/               # Clinical protocol markdowns (.md)
│
└── utils/
    └── helpers.py               # Decorators, sanitizers, formatting helpers
│
└── tests/
    └── test_api.py              # Unit & integration tests for API endpoints
```

---

## API Endpoints Reference

### 1. Authentication (`/api/auth`)
- `POST /api/auth/login`: Authenticates user credentials, sets session cookies, and returns JWT access token.
- `POST /api/auth/signup`: Registers new user account with role-specific privileges.
- `GET /api/auth/me`: Inspects currently authenticated user profile.
- `POST /api/auth/logout`: Invalidates session and clears cookies.

### 2. Clinical Case Management (`/api/cases`)
- `GET /api/cases`: Filterable case directory by status, priority, language, or search query.
- `POST /api/cases`: Creates case with automated safety rule evaluation and patient self-admission check.
- `GET /api/cases/{case_id}`: Retrieves comprehensive patient case dossier.
- `PATCH /api/cases/{case_id}`: Partially updates clinical parameters.
- `POST /api/cases/{case_id}/approve-admission`: Frontline nurse verifies vitals and admits patient to doctor review queue.
- `POST /api/cases/{case_id}/review`: Doctor clinical assessment (`reviewed`, `escalate`, `referral`).
- `POST /api/cases/{case_id}/referral`: Dispatches specialized referral routing packet.

### 3. Multimodal Intake & Analysis (`/api`)
- `POST /api/process-audio`: Transcribes speech audio, cleans disfluencies, and synthesizes clinical chief complaint.
- `POST /api/process-document`: OCR parsing for chest X-rays, CBC lab slips, and prescriptions.
- `POST /api/cases/{case_id}/analyze`: End-to-end multimodal entity extraction and safety evaluation.
- `POST /api/patient/diet-advice`: Synthesizes personalized nutrition guidelines based on physiological vitals.

### 4. RAG Protocol Retrieval (`/api/rag`)
- `POST /api/rag/search`: Queries ChromaDB vector store for evidence-based emergency protocols.
- `GET /api/rag/documents`: Lists indexed clinical guidelines and chunk count.
- `POST /api/rag/upload`: Uploads and chunks new clinical protocol documents.
- `POST /api/rag/reindex`: Rebuilds vector index from all protocol files.

### 5. Clinical Reports & PDF Export (`/api/reports`)
- `GET /api/reports/{case_id}/dossier`: Generates 15-section standardized clinical handoff JSON.
- `GET /api/reports/{case_id}/pdf`: Generates and streams downloadable ReportLab PDF handoff document.

---

## Running Backend Tests
```bash
python -m unittest backend/tests/test_api.py
```
