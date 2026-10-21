"""
config.py — Central configuration for Rural Legal Aid Summarizer.

NOTE (Free-Tier Privacy): Prompts sent to Gemini free tier may be used by Google
to improve their models. Do NOT use this app for highly sensitive documents
without upgrading to a paid Gemini API tier. To swap model/tier, change only the
constants below.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
load_dotenv()  # fallback to current dir

# ── Windows: Tesseract path hint ──────────────────────────────────────────────
# If Tesseract is installed but not on PATH, uncomment and set the path below.
# Default Windows install location:
# import pytesseract
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
UPLOAD_DIR   = BASE_DIR / "uploads"
AUDIO_DIR    = BASE_DIR / "uploads" / "audio"
CHROMA_DIR   = BASE_DIR / "chroma_db"
SQLITE_PATH  = BASE_DIR / "database" / "legal_aid.db"
DOCS_DIR     = BASE_DIR.parent / "legal_documents"

# ── File upload limits ─────────────────────────────────────────────────────────
MAX_CONTENT_LENGTH = 16 * 1024 * 1024   # 16 MB — safe on 8 GB RAM
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "txt"}

# ── Gemini — swap model/tier here only ────────────────────────────────────────
# NOTE: Do NOT use gemini-2.5-flash — deprecated / intermittent outages.
GEMINI_API_KEY           = os.getenv("GEMINI_API_KEY", "")
GEMINI_SUMMARY_MODEL = "gemini-3.5-flash-lite"
GEMINI_REASONING_MODEL = "gemini-3.5-flash-lite"   # follow-up Q&A / harder reasoning
GEMINI_TEMPERATURE       = 0.2
GEMINI_MAX_OUTPUT_TOKENS = 4096

# ── Free-tier rate limiting ───────────────────────────────────────────────────
GEMINI_RPM_LIMIT   = 15   # requests per minute (conservative free-tier estimate)
GEMINI_MAX_RETRIES = 4
GEMINI_BACKOFF_BASE = 2   # seconds; exponential: 2, 4, 8, 16 …

# ── RAG / Embeddings ──────────────────────────────────────────────────────────
EMBED_MODEL      = "BAAI/bge-small-en-v1.5"   # lightweight, avoids full PyTorch
CHROMA_COLLECTION = "legal_documents"
TOP_K_VECTOR     = 5    # results from ChromaDB
TOP_K_BM25       = 5    # results from BM25 pass
TOP_K_FINAL      = 5    # merged/re-ranked results sent to Gemini

# ── Languages supported ───────────────────────────────────────────────────────
SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "mr": "Marathi",
}
GTTS_LANG_MAP = {
    "en": "en",
    "hi": "hi",
    "mr": "mr",
}

# ── OCR ───────────────────────────────────────────────────────────────────────
TESSERACT_LANG = "eng+hin+mar"
OCR_MIN_CHARS  = 50   # if PyMuPDF returns fewer chars, fall back to OCR
