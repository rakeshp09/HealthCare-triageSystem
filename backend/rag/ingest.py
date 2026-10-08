"""Protocol Document Chunking and Vector Store Ingestion Module.

Reads clinical protocol markdowns from backend/rag/documents/, chunks them semantically,
and indexes vectors into ChromaDB collection 'clinical_protocols'.
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List
from .chroma_client import chroma_manager

DOCUMENTS_DIR = Path(__file__).resolve().parent / "documents"

def chunk_markdown(content: str, source_filename: str) -> List[Dict[str, Any]]:
    """Chunks markdown by header sections (##) with metadata."""
    chunks = []
    lines = content.splitlines()
    
    current_title = source_filename.replace(".md", "").replace("_", " ").title()
    current_section = "Overview"
    current_text = []

    for line in lines:
        if line.startswith("# "):
            current_title = line.replace("#", "").strip()
        elif line.startswith("## "):
            if current_text:
                chunk_body = "\n".join(current_text).strip()
                if len(chunk_body) > 30:
                    chunks.append({
                        "title": current_title,
                        "section": current_section,
                        "content": f"Protocol: {current_title}\nSection: {current_section}\n\n{chunk_body}",
                        "source": source_filename
                    })
                current_text = []
            current_section = line.replace("##", "").strip()
        else:
            current_text.append(line)

    if current_text:
        chunk_body = "\n".join(current_text).strip()
        if len(chunk_body) > 30:
            chunks.append({
                "title": current_title,
                "section": current_section,
                "content": f"Protocol: {current_title}\nSection: {current_section}\n\n{chunk_body}",
                "source": source_filename
            })

    return chunks

def ingest_protocols() -> Dict[str, Any]:
    """Ingests all markdown documents from backend/rag/documents/ into ChromaDB."""
    collection = chroma_manager.get_protocol_collection()
    if not collection:
        return {"success": False, "indexed_chunks": 0, "error": "ChromaDB collection unavailable"}

    all_chunks = []
    if os.path.exists(DOCUMENTS_DIR):
        for fname in os.listdir(DOCUMENTS_DIR):
            if fname.endswith(".md") or fname.endswith(".txt"):
                fpath = DOCUMENTS_DIR / fname
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        text = f.read()
                    chunks = chunk_markdown(text, fname)
                    all_chunks.extend(chunks)
                except Exception as e:
                    print(f"[Ingest] Error reading {fname}: {e}")

    if not all_chunks:
        return {"success": True, "indexed_chunks": 0, "message": "No protocol documents found"}

    ids = [f"proto_{idx}_{c['source']}" for idx, c in enumerate(all_chunks)]
    documents = [c["content"] for c in all_chunks]
    metadatas = [{"title": c["title"], "section": c["section"], "source": c["source"]} for c in all_chunks]

    try:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return {
            "success": True,
            "indexed_chunks": len(all_chunks),
            "files_processed": len(set(c["source"] for c in all_chunks))
        }
    except Exception as e:
        print(f"[Ingest] Ingestion error: {e}")
        return {"success": False, "indexed_chunks": 0, "error": str(e)}

if __name__ == "__main__":
    res = ingest_protocols()
    print("Ingest result:", res)
