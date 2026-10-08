"""RAG Knowledge Base and Vector Search Router.

Provides vector similarity search across clinical emergency protocols and historical cases,
protocol document uploads, and automated reindexing.
"""

import os
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from .schemas import RAGQueryRequest
from ..rag.retriever import rag_retriever
from ..rag.ingest import ingest_protocols, DOCUMENTS_DIR, chunk_markdown
from ..rag.chroma_client import chroma_manager
from ..utils.helpers import sanitize_filename

router = APIRouter(prefix="/api", tags=["RAG & Semantic Retrieval"])

@router.post("/rag/search")
@router.post("/search/semantic")
@router.get("/search/semantic")
def search_semantic(
    payload: Optional[RAGQueryRequest] = None,
    q: Optional[str] = None,
    query: Optional[str] = None
):
    """Performs vector similarity search across evidence-based protocols and clinical cases."""
    search_text = (payload.query if payload else None) or q or query or ""
    if not search_text.strip():
        return {"success": False, "results": [], "error": "Search query required"}

    n_results = payload.n_results if payload else 5
    collection_target = (payload.collection if payload else "clinical_protocols") or "clinical_protocols"

    if collection_target == "clinical_cases":
        results = rag_retriever.retrieve_similar_cases(search_text, n_results=n_results)
    else:
        results = rag_retriever.retrieve_protocols(search_text, n_results=n_results)

    return {
        "success": True,
        "query": search_text,
        "count": len(results),
        "results": results
    }

@router.get("/rag/documents")
def list_protocol_documents():
    """Lists all available evidence-based clinical protocols."""
    docs = []
    if os.path.exists(DOCUMENTS_DIR):
        for fname in sorted(os.listdir(DOCUMENTS_DIR)):
            if fname.endswith(".md") or fname.endswith(".txt"):
                fpath = DOCUMENTS_DIR / fname
                size_bytes = os.path.getsize(fpath)
                docs.append({
                    "filename": fname,
                    "title": fname.replace(".md", "").replace("_", " ").title(),
                    "size_bytes": size_bytes,
                    "format": "Markdown Protocol"
                })
    col = chroma_manager.get_protocol_collection()
    chunk_count = col.count() if col else 0
    return {
        "success": True,
        "documents": docs,
        "total_documents": len(docs),
        "total_indexed_chunks": chunk_count
    }

@router.post("/rag/upload")
async def upload_protocol_document(file: UploadFile = File(...)):
    """Uploads a new clinical guideline or protocol and indexes it into the vector database."""
    fname = sanitize_filename(file.filename or "new_protocol.md")
    if not (fname.endswith(".md") or fname.endswith(".txt")):
        raise HTTPException(status_code=400, detail="Only Markdown (.md) or Text (.txt) protocols are supported")

    save_path = DOCUMENTS_DIR / fname
    contents = await file.read()
    text = contents.decode("utf-8", errors="ignore")

    with open(save_path, "w", encoding="utf-8") as f:
        f.write(text)

    # Chunk and index immediately
    chunks = chunk_markdown(text, fname)
    col = chroma_manager.get_protocol_collection()
    if col and chunks:
        ids = [f"proto_{idx}_{fname}" for idx in range(len(chunks))]
        docs = [c["content"] for c in chunks]
        metas = [{"title": c["title"], "section": c["section"], "source": fname} for c in chunks]
        col.upsert(ids=ids, documents=docs, metadatas=metas)

    return {
        "success": True,
        "filename": fname,
        "chunks_indexed": len(chunks),
        "message": f"Clinical protocol '{fname}' successfully indexed into RAG store."
    }

@router.post("/rag/reindex")
def reindex_all_protocols():
    """Rebuilds the ChromaDB vector index from all protocol documents."""
    result = ingest_protocols()
    return result
