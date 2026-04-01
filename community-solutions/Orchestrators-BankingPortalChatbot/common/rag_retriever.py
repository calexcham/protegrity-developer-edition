"""
Shared RAG retriever using ChromaDB over pre-protected knowledge base files.

All orchestrators use this for semantic search over tokenized ticket/customer data.
"""

from __future__ import annotations

import os
import glob
from typing import List

_CHROMA_CLIENT = None
_COLLECTION = None

KB_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "banking_data", "knowledge_base",
)
CHROMA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "chroma_db",
)


def _get_collection():
    """Lazy-init ChromaDB collection from pre-protected KB files."""
    global _CHROMA_CLIENT, _COLLECTION
    if _COLLECTION is not None:
        return _COLLECTION

    try:
        import chromadb
    except ImportError:
        raise ImportError("pip install chromadb")

    try:
        _CHROMA_CLIENT = chromadb.PersistentClient(path=CHROMA_DIR)
    except Exception:
        # Stale/corrupted DB — wipe and retry
        import shutil
        if os.path.exists(CHROMA_DIR):
            shutil.rmtree(CHROMA_DIR)
        _CHROMA_CLIENT = chromadb.PersistentClient(path=CHROMA_DIR)

    try:
        _COLLECTION = _CHROMA_CLIENT.get_collection("banking_kb")
        return _COLLECTION
    except Exception:
        pass

    # Build from KB files
    _COLLECTION = _CHROMA_CLIENT.get_or_create_collection("banking_kb")
    kb_files = sorted(glob.glob(os.path.join(KB_DIR, "*.txt")))

    if not kb_files:
        raise FileNotFoundError(f"No KB files found in {KB_DIR}")

    ids, docs, metas = [], [], []
    for fpath in kb_files:
        cust_id = os.path.splitext(os.path.basename(fpath))[0]
        with open(fpath, "r") as f:
            content = f.read()
        ids.append(cust_id)
        docs.append(content)
        metas.append({"customer_id": cust_id, "source": fpath})

    _COLLECTION.add(ids=ids, documents=docs, metadatas=metas)
    return _COLLECTION


def retrieve(query: str, top_k: int = 3, customer_id: str = None) -> List[dict]:
    """Semantic search over pre-protected KB. Optionally filter by customer_id."""
    collection = _get_collection()

    where_filter = {"customer_id": customer_id} if customer_id else None
    results = collection.query(query_texts=[query], n_results=top_k, where=where_filter)

    output = []
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i] if results["metadatas"] else {}
        dist = results["distances"][0][i] if results.get("distances") else None
        output.append({"text": doc, "metadata": meta, "distance": dist})
    return output


def rebuild_index() -> int:
    """Force rebuild ChromaDB index from KB files."""
    global _COLLECTION, _CHROMA_CLIENT
    _COLLECTION = None
    _CHROMA_CLIENT = None

    import shutil
    if os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)

    _get_collection()
    return _COLLECTION.count()
