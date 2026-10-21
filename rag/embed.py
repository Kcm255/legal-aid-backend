"""
rag/embed.py — fastembed embeddings using BAAI/bge-small-en-v1.5.

Uses fastembed instead of sentence-transformers to avoid pulling in full PyTorch,
which would be too heavy for an 8GB RAM machine without a dedicated GPU.

The embedder is a module-level singleton (loaded once, reused across requests).
"""
from config import EMBED_MODEL

_embedder = None


def get_embedder():
    """Lazy-load and return the fastembed embedder singleton."""
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding
        print(f"[embed] Loading fastembed model: {EMBED_MODEL}")
        _embedder = TextEmbedding(model_name=EMBED_MODEL)
        print("[embed] Model loaded.")
    return _embedder


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of text strings.

    Returns:
        List of embedding vectors (list of floats).
    """
    embedder = get_embedder()
    embeddings = list(embedder.embed(texts))
    return [e.tolist() for e in embeddings]


def embed_query(query: str) -> list[float]:
    """Embed a single query string."""
    return embed_texts([query])[0]
