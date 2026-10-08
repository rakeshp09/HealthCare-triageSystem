"""Vector Similarity Retriever and Hybrid Search Module.

Retrieves top-k evidence-based clinical protocols and historical cases
grounded in query semantics.
"""

from typing import Dict, Any, List, Optional
from .chroma_client import chroma_manager

class RAGRetriever:
    """Retrieves relevant clinical protocol chunks and historical case records."""

    def __init__(self):
        self.chroma = chroma_manager

    def retrieve_protocols(self, query: str, n_results: int = 4) -> List[Dict[str, Any]]:
        """Retrieves top matching clinical protocols for a clinical query or symptom set."""
        col = self.chroma.get_protocol_collection()
        if not col or not query:
            return []

        try:
            count = col.count()
            if count == 0:
                return []
            
            res = col.query(
                query_texts=[query],
                n_results=min(n_results, count)
            )

            hits = []
            if res and "ids" in res and res["ids"]:
                ids = res["ids"][0]
                docs = res.get("documents", [[]])[0]
                metas = res.get("metadatas", [[]])[0]
                distances = res.get("distances", [[]])[0] if "distances" in res else []

                for i in range(len(ids)):
                    hits.append({
                        "id": ids[i],
                        "content": docs[i] if i < len(docs) else "",
                        "title": metas[i].get("title", "Clinical Protocol") if i < len(metas) else "Protocol",
                        "section": metas[i].get("section", "Guidelines") if i < len(metas) else "Guidelines",
                        "source": metas[i].get("source", "") if i < len(metas) else "",
                        "score": round(1.0 - (distances[i] if i < len(distances) else 0.5), 3)
                    })
            return hits
        except Exception as e:
            print(f"[RAGRetriever] Retrieval error: {e}")
            return []

    def retrieve_similar_cases(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Retrieves clinically similar past patient presentations."""
        col = self.chroma.get_case_collection()
        if not col or not query:
            return []

        try:
            count = col.count()
            if count == 0:
                return []

            res = col.query(
                query_texts=[query],
                n_results=min(n_results, count)
            )

            hits = []
            if res and "ids" in res and res["ids"]:
                ids = res["ids"][0]
                docs = res.get("documents", [[]])[0]
                metas = res.get("metadatas", [[]])[0]

                for i in range(len(ids)):
                    hits.append({
                        "id": ids[i],
                        "summary": docs[i] if i < len(docs) else "",
                        "metadata": metas[i] if i < len(metas) else {}
                    })
            return hits
        except Exception as e:
            print(f"[RAGRetriever] Case search error: {e}")
            return []

    def index_case(self, case_id: str, case_text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Indexes a clinical case summary into ChromaDB for future similarity matching."""
        col = self.chroma.get_case_collection()
        if not col or not case_id or not case_text:
            return False

        clean_meta = {}
        if metadata:
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    clean_meta[k] = v
                else:
                    clean_meta[k] = str(v)

        try:
            col.upsert(
                ids=[str(case_id)],
                documents=[case_text],
                metadatas=[clean_meta] if clean_meta else None
            )
            return True
        except Exception as e:
            print(f"[RAGRetriever] index_case error: {e}")
            return False

rag_retriever = RAGRetriever()
