"""
rag/ingest.py — Chunk and embed legal documents into ChromaDB.

Run this script directly to seed the knowledge base:
    python backend/rag/ingest.py

Supported file types in legal_documents/:
  .txt  — plain text (fastest, no dependencies)
  .pdf  — extracted via PyMuPDF (digital PDFs) or OCR fallback (scanned PDFs)
  .jpg / .jpeg / .png — OCR via OpenCV + PyTesseract

Just drop any of these file types into a category subfolder under legal_documents/
and re-run this script. It uses upsert so it is safe to re-run without duplicates.

Folder structure example:
  legal_documents/
    acts/
      rti_act.pdf
      consumer_protection_act.txt
    banking/
      rbi_loan_notice.pdf
    court_notices/
      summons_sample.jpg
"""
import sys
import re
from pathlib import Path

# Allow running as a script from the backend directory
sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb
from config import CHROMA_DIR, CHROMA_COLLECTION, DOCS_DIR
from rag.embed import embed_texts

CHUNK_SIZE = 400   # approximate max chars per chunk
MIN_CHUNK  = 80    # discard chunks shorter than this

# Supported extensions
SUPPORTED_EXTS = {".txt", ".pdf", ".jpg", ".jpeg", ".png"}


def _extract_text_from_file(file_path: Path) -> str:
    """
    Extract raw text from a file based on its extension.
    Returns empty string on failure (with a warning printed).
    """
    ext = file_path.suffix.lower()

    if ext == ".txt":
        return file_path.read_text(encoding="utf-8", errors="ignore")

    elif ext == ".pdf":
        # Use the same extraction pipeline as the main app
        from extraction.extractor import extract_text
        result = extract_text(file_path)
        if result["error"]:
            print(f"  [warn] {file_path.name}: {result['error']}")
        return result.get("text", "")

    elif ext in {".jpg", ".jpeg", ".png"}:
        from extraction.ocr_extractor import extract_text_from_image
        try:
            return extract_text_from_image(file_path)
        except Exception as e:
            print(f"  [warn] {file_path.name}: OCR failed — {e}")
            return ""

    return ""


def _split_into_chunks(text: str) -> list[str]:
    """Split text into chunks suitable for embedding."""
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]

    chunks = []
    for para in paragraphs:
        if len(para) <= CHUNK_SIZE:
            if len(para) >= MIN_CHUNK:
                chunks.append(para)
        else:
            sentences = re.split(r'(?<=[.!?।])\s+', para)
            current = ""
            for sent in sentences:
                if len(current) + len(sent) <= CHUNK_SIZE:
                    current += (" " if current else "") + sent
                else:
                    if len(current) >= MIN_CHUNK:
                        chunks.append(current.strip())
                    current = sent
            if len(current) >= MIN_CHUNK:
                chunks.append(current.strip())
    return chunks


def _get_chroma_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )
    return collection


def ingest_file(file_path: Path, category: str, collection) -> int:
    """Extract, chunk, embed, and upsert a single document. Returns chunk count."""
    print(f"  [reading] {file_path.name} ({file_path.suffix.upper()[1:]})")

    text = _extract_text_from_file(file_path)
    if not text.strip():
        print(f"  [skip] {file_path.name} — could not extract text")
        return 0

    chunks = _split_into_chunks(text)
    if not chunks:
        print(f"  [skip] {file_path.name} — no usable chunks after splitting")
        return 0

    embeddings = embed_texts(chunks)

    stem = file_path.stem
    ids = [f"{category}::{stem}::{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "source":      file_path.name,
            "category":    category,
            "chunk_index": i,
            "file_type":   file_path.suffix.lower().lstrip("."),
        }
        for i in range(len(chunks))
    ]

    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    print(f"  [ok] {file_path.name} — {len(chunks)} chunks ingested")
    return len(chunks)


def ingest_all(docs_dir: Path = DOCS_DIR) -> None:
    """
    Walk legal_documents/ and ingest all supported files.
    Supported: .txt, .pdf, .jpg, .jpeg, .png
    """
    collection = _get_chroma_collection()
    total = 0
    skipped = 0

    if not docs_dir.exists():
        print(f"[ingest] Documents directory not found: {docs_dir}")
        print(f"[ingest] Expected path: {docs_dir.resolve()}")
        print("[ingest] Create the folder and add documents, then re-run.")
        return

    for category_dir in sorted(docs_dir.iterdir()):
        if not category_dir.is_dir():
            continue
        category = category_dir.name
        files = [f for f in sorted(category_dir.iterdir())
                 if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS]

        if not files:
            print(f"\n[ingest] Category '{category}' — no supported files found")
            print(f"         (Drop .txt / .pdf / .jpg / .png files into {category_dir})")
            continue

        print(f"\n[ingest] Category: {category} ({len(files)} file(s))")
        for f in files:
            count = ingest_file(f, category, collection)
            if count:
                total += count
            else:
                skipped += 1

    print(f"\n{'='*50}")
    print(f"[ingest] Done. Chunks ingested: {total} | Files skipped: {skipped}")
    print(f"[ingest] ChromaDB stored at: {CHROMA_DIR.resolve()}")


if __name__ == "__main__":
    print("[ingest] Starting knowledge base ingestion…")
    print(f"[ingest] Looking for documents in: {DOCS_DIR.resolve()}")
    ingest_all()

