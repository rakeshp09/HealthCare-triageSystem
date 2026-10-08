"""ChromaDB Persistent Client and Collection Manager.

Manages persistent vector collections for clinical protocols and case dossiers
with automatic fallback to EphemeralClient.
"""

import os
from typing import Optional
from ..app.config import settings

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    _CHROMADB_AVAILABLE = True
except Exception:
    chromadb = None
    _CHROMADB_AVAILABLE = False

class ChromaManager:
    """Manages ChromaDB collections and connection states."""

    def __init__(self):
        self.is_available = _CHROMADB_AVAILABLE
        self._client = None
        self._protocol_col = None
        self._case_col = None
        self.persist_dir = str(settings.CHROMADB_DIR)

    def get_client(self):
        """Initializes or returns active ChromaDB client."""
        if not self.is_available:
            return None

        if self._client is None:
            try:
                os.makedirs(self.persist_dir, exist_ok=True)
                self._client = chromadb.PersistentClient(path=self.persist_dir)
            except Exception as e:
                print(f"[ChromaManager] PersistentClient error: {e}. Falling back to EphemeralClient.")
                try:
                    self._client = chromadb.EphemeralClient()
                except Exception as inner_e:
                    print(f"[ChromaManager] EphemeralClient initialization error: {inner_e}")
                    self._client = None
        return self._client

    def get_protocol_collection(self):
        """Returns the collection containing evidence-based clinical protocols."""
        client = self.get_client()
        if not client:
            return None
        if self._protocol_col is None:
            try:
                self._protocol_col = client.get_or_create_collection(
                    name="clinical_protocols",
                    metadata={"description": "Standardized Clinical Triage Protocols and Emergency Guidelines"}
                )
            except Exception as e:
                print(f"[ChromaManager] Failed to get protocol collection: {e}")
        return self._protocol_col

    def get_case_collection(self):
        """Returns the collection containing vectorized patient triage cases."""
        client = self.get_client()
        if not client:
            return None
        if self._case_col is None:
            try:
                self._case_col = client.get_or_create_collection(
                    name="clinical_cases",
                    metadata={"description": "Vectorized Patient Triage Case History"}
                )
            except Exception as e:
                print(f"[ChromaManager] Failed to get case collection: {e}")
        return self._case_col

chroma_manager = ChromaManager()
