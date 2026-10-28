"""
check_setup.py — Quick validation script to verify all modules import correctly
and the environment is configured.

Run from the backend/ directory:
    python check_setup.py
"""
import sys
import os
from pathlib import Path

# Force UTF-8 output on Windows (avoids cp1252 emoji errors)
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

errors = []
warnings = []

print("=" * 55)
print("  Rural Legal Aid Summarizer — Setup Checker")
print("=" * 55)


def check(label, fn):
    try:
        result = fn()
        status = result if isinstance(result, str) else "✅ OK"
        print(f"  {status:<8}  {label}")
    except Exception as e:
        print(f"  ❌ FAIL  {label}")
        print(f"           {e}")
        errors.append(label)


# ── Core imports ──────────────────────────────────────────────────────────────
print("\n[1] Core Python modules")

check("Flask", lambda: __import__("flask") and "✅ OK")
check("Flask-CORS", lambda: __import__("flask_cors") and "✅ OK")
check("python-dotenv", lambda: __import__("dotenv") and "✅ OK")
check("Werkzeug", lambda: __import__("werkzeug") and "✅ OK")

# ── Document extraction ───────────────────────────────────────────────────────
print("\n[2] Document extraction")

check("PyMuPDF (fitz)", lambda: __import__("fitz") and "✅ OK")
check("Pillow", lambda: __import__("PIL") and "✅ OK")
check("OpenCV", lambda: __import__("cv2") and "✅ OK")
check("NumPy", lambda: __import__("numpy") and "✅ OK")

def check_tesseract():
    import pytesseract
    version = pytesseract.get_tesseract_version()
    return f"✅ v{version}"
check("PyTesseract", check_tesseract)

def check_tesseract_langs():
    import pytesseract
    langs = pytesseract.get_languages()
    missing = [l for l in ["eng", "hin", "mar"] if l not in langs]
    if missing:
        warnings.append(f"Tesseract missing language packs: {missing}")
        return f"⚠️  Missing: {missing}"
    return "✅ eng+hin+mar"
check("Tesseract lang packs", check_tesseract_langs)

def check_pdf2image():
    import pdf2image
    return "✅ OK"
check("pdf2image", check_pdf2image)

# ── AI & RAG ──────────────────────────────────────────────────────────────────
print("\n[3] AI & RAG")

check("fastembed", lambda: __import__("fastembed") and "✅ OK")
check("chromadb", lambda: __import__("chromadb") and "✅ OK")
check("rank-bm25", lambda: __import__("rank_bm25") and "✅ OK")

# ── Audio ─────────────────────────────────────────────────────────────────────
print("\n[4] Audio")
check("pyttsx3", lambda: __import__("pyttsx3") and "✅ OK")

# ── Config & env ──────────────────────────────────────────────────────────────
print("\n[5] Configuration")

def check_llm_config():
    from config import LLM_PROVIDER, LLM_MODEL, LLM_BASE_URL
    if LLM_PROVIDER != "ollama":
        return f"⚠️  Unsupported provider: {LLM_PROVIDER}"
    return f"✅ {LLM_MODEL} at {LLM_BASE_URL}"
check("Ollama LLM configuration", check_llm_config)

def check_dirs():
    from config import UPLOAD_DIR, AUDIO_DIR, CHROMA_DIR, DOCS_DIR
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return "✅ OK"
check("Required directories", check_dirs)

def check_legal_docs():
    from config import DOCS_DIR
    if not DOCS_DIR.exists():
        return "⚠️  legal_documents/ folder not found"
    pdf_count = sum(1 for _ in DOCS_DIR.rglob("*.pdf"))
    txt_count = sum(1 for _ in DOCS_DIR.rglob("*.txt"))
    img_count = sum(1 for _ in DOCS_DIR.rglob("*.jpg")) + sum(1 for _ in DOCS_DIR.rglob("*.png"))
    total = pdf_count + txt_count + img_count
    if total == 0:
        warnings.append("No documents found in legal_documents/ — RAG will have no context")
        return "⚠️  Empty (add PDFs to legal_documents/)"
    return f"✅ {pdf_count} PDFs, {txt_count} TXTs, {img_count} images"
check("Knowledge base docs", check_legal_docs)

def check_chroma():
    from config import CHROMA_DIR, CHROMA_COLLECTION
    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    col = client.get_or_create_collection(CHROMA_COLLECTION)
    count = col.count()
    if count == 0:
        warnings.append("ChromaDB is empty — run: cd backend && python rag/ingest.py")
        return f"⚠️  Empty (run ingest.py)"
    return f"✅ {count} chunks indexed"
check("ChromaDB", check_chroma)

# ── App modules ───────────────────────────────────────────────────────────────
print("\n[6] App modules")
check("database.db", lambda: __import__("database.db") and "✅ OK")
check("extraction.extractor", lambda: __import__("extraction.extractor") and "✅ OK")
check("rag.embed", lambda: __import__("rag.embed") and "✅ OK")
check("rag.retrieve", lambda: __import__("rag.retrieve") and "✅ OK")
check("ai.llm", lambda: __import__("ai.llm") and "✅ OK")
check("ai.prompts", lambda: __import__("ai.prompts") and "✅ OK")
check("ai.processor", lambda: __import__("ai.processor") and "✅ OK")
check("audio.tts", lambda: __import__("audio.tts") and "✅ OK")

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 55)
if errors:
    print(f"  ❌ {len(errors)} error(s) found — fix before running:")
    for e in errors:
        print(f"     • {e}")
else:
    print("  ✅ All critical checks passed!")

if warnings:
    print(f"\n  ⚠️  {len(warnings)} warning(s):")
    for w in warnings:
        print(f"     • {w}")

if not errors and not warnings:
    print("\n  🚀 Ready to run:")
    print("     Backend:  cd backend && python app.py")
    print("     Frontend: cd frontend && npm run dev")
elif not errors:
    print("\n  🚀 Can still run (warnings are non-blocking):")
    print("     Backend:  cd backend && python app.py")
    print("     Frontend: cd frontend && npm run dev")

print("=" * 55)
