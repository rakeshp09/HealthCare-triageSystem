"""Backend Services Package.

Exports modular services for LLM reasoning, vector embeddings, speech recognition,
vision OCR, clinical entity extraction, multilingual translation, RAG retrieval, and clinical safety.
"""

from .llm_service import llm_service, LLMService
from .embedding_service import embedding_service, EmbeddingService
from .speech_service import speech_service, SpeechService, format_chief_clinical_concern
from .vision_service import vision_service, VisionService
from .extraction_service import extraction_service, ExtractionService
from .language_service import language_service, LanguageService
from .rag_service import rag_service, RAGService
from .safety_service import safety_service, SafetyService

__all__ = [
    "llm_service",
    "LLMService",
    "embedding_service",
    "EmbeddingService",
    "speech_service",
    "SpeechService",
    "format_chief_clinical_concern",
    "vision_service",
    "VisionService",
    "extraction_service",
    "ExtractionService",
    "language_service",
    "LanguageService",
    "rag_service",
    "RAGService",
    "safety_service",
    "SafetyService"
]
