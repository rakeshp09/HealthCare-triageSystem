"""Vector Embeddings and Semantic Representation Service.

Generates dense vector embeddings for clinical protocol matching and case retrieval.
"""

from typing import List, Optional
import os
from ..app.config import settings

try:
    from sentence_transformers import SentenceTransformer
    _SENTENCE_TRANSFORMERS_AVAILABLE = True
except Exception:
    SentenceTransformer = None
    _SENTENCE_TRANSFORMERS_AVAILABLE = False

class EmbeddingService:
    """Generates dense vector embeddings for clinical text."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self.is_available = _SENTENCE_TRANSFORMERS_AVAILABLE

    def _get_model(self):
        if not self.is_available:
            return None
        if self._model is None:
            try:
                self._model = SentenceTransformer(self.model_name)
            except Exception as e:
                print(f"[EmbeddingService] Note on local model load: {e}")
                self._model = None
        return self._model

    def embed_text(self, text: str) -> Optional[List[float]]:
        """Generates embedding vector for a single string."""
        if not text:
            return None
        model = self._get_model()
        if model is not None:
            try:
                emb = model.encode(text)
                return emb.tolist()
            except Exception as e:
                print(f"[EmbeddingService] Encoding error: {e}")
        return None

    def embed_documents(self, documents: List[str]) -> Optional[List[List[float]]]:
        """Generates embeddings for a batch of documents."""
        model = self._get_model()
        if model is not None and documents:
            try:
                embeddings = model.encode(documents)
                return [emb.tolist() for emb in embeddings]
            except Exception as e:
                print(f"[EmbeddingService] Batch encoding error: {e}")
        return None

embedding_service = EmbeddingService()
