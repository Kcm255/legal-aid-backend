"""
rag/retrieve.py — Hybrid retrieval: ChromaDB vector search + BM25 keyword search.

Legal text depends heavily on exact terminology (act names, section numbers).
Pure embedding similarity can miss these, so we merge:
  1. ChromaDB cosine similarity search (semantic)
  2. BM25 keyword search over the same corpus
  3. Reciprocal Rank Fusion (RRF) to merge and re-rank results
"""
import chromadb
from rank_bm25 import BM25Okapi
from config import CHROMA_DIR, CHROMA_COLLECTION, TOP_K_VECTOR, TOP_K_BM25, TOP_K_FINAL
from rag.embed import embed_query

_chroma_client = None
_collection = None
_bm25_index = None
_bm25_docs = None
_bm25_ids = None


def _get_collection():
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = _chroma_client.get_or_create_collection(
            name=CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"}
        )
    return _collection


def _get_bm25_index():
    """Build/cache a BM25 index over all documents in ChromaDB."""
    global _bm25_index, _bm25_docs, _bm25_ids
    if _bm25_index is None:
        collection = _get_collection()
        result = collection.get(include=["documents", "metadatas"])
        docs = result.get("documents", [])
        ids = result.get("ids", [])
        if not docs:
            return None, [], []
        tokenized = [doc.lower().split() for doc in docs]
        _bm25_index = BM25Okapi(tokenized)
        _bm25_docs = docs
        _bm25_ids = ids
    return _bm25_index, _bm25_docs, _bm25_ids


def _rrf_merge(vector_results: list[dict], bm25_results: list[dict], k: int = 60) -> list[dict]:
    """
    Reciprocal Rank Fusion merge.
    Each result dict must have keys: 'id', 'text', 'metadata'.
    """
    scores: dict[str, float] = {}
    doc_map: dict[str, dict] = {}

    for rank, item in enumerate(vector_results):
        doc_id = item["id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
        doc_map[doc_id] = item

    for rank, item in enumerate(bm25_results):
        doc_id = item["id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
        doc_map[doc_id] = item

    ranked_ids = sorted(scores, key=scores.__getitem__, reverse=True)
    return [doc_map[doc_id] for doc_id in ranked_ids[:TOP_K_FINAL]]


def retrieve(query: str) -> list[dict]:
    """
    Hybrid retrieval for a query string.

    Returns:
        List of dicts: [{"id", "text", "metadata", "source"}]
    """
    collection = _get_collection()
    
    # 1. Vector search
    query_embedding = embed_query(query)
    vector_res = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(TOP_K_VECTOR, collection.count() or 1),
        include=["documents", "metadatas", "distances"],
    )
    
    vector_results = []
    if vector_res and vector_res.get("ids"):
        for i, doc_id in enumerate(vector_res["ids"][0]):
            vector_results.append({
                "id": doc_id,
                "text": vector_res["documents"][0][i],
                "metadata": vector_res["metadatas"][0][i],
            })

    # 2. BM25 keyword search
    bm25_results = []
    bm25_index, bm25_docs, bm25_ids = _get_bm25_index()
    if bm25_index and bm25_docs:
        tokenized_query = query.lower().split()
        scores = bm25_index.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:TOP_K_BM25]
        for idx in top_indices:
            if scores[idx] > 0:
                bm25_results.append({
                    "id": bm25_ids[idx],
                    "text": bm25_docs[idx],
                    "metadata": {},
                })

    # 3. RRF merge
    if not vector_results and not bm25_results:
        return []

    merged = _rrf_merge(vector_results, bm25_results)
    return merged


def get_context_chunks(query: str) -> list[str]:
    """Convenience wrapper — returns just the text chunks for Gemini prompts."""
    results = retrieve(query)
    return [r["text"] for r in results]


def invalidate_bm25_cache():
    """Call after ingesting new documents to rebuild BM25 index on next query."""
    global _bm25_index, _bm25_docs, _bm25_ids, _collection
    _bm25_index = None
    _bm25_docs = None
    _bm25_ids = None
    _collection = None
