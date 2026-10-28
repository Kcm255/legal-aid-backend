"""Central configuration for Rural Legal Aid Summarizer."""
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

# ── Local/remote Ollama Qwen server ──────────────────────────────────────────
LLM_PROVIDER          = os.getenv("LLM_PROVIDER", "ollama").lower()
LLM_MODEL             = os.getenv("LLM_MODEL", "qwen3:14b")
# The model runs on the second device. This may be overridden in .env for a
# different deployment, but a fresh checkout should use the working server.
LLM_BASE_URL          = os.getenv("LLM_BASE_URL", "http://10.210.8.172:9050")
LLM_TIMEOUT            = int(os.getenv("LLM_TIMEOUT", "180"))
LLM_TEMPERATURE       = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_MAX_OUTPUT_TOKENS = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "4096"))
LLM_MAX_RETRIES       = int(os.getenv("LLM_MAX_RETRIES", "2"))

# ── RAG / Embeddings ──────────────────────────────────────────────────────────
EMBED_MODEL      = "BAAI/bge-small-en-v1.5"   # lightweight, avoids full PyTorch
CHROMA_COLLECTION = "legal_documents"
TOP_K_VECTOR     = 5    # results from ChromaDB
TOP_K_BM25       = 5    # results from BM25 pass
TOP_K_FINAL      = 5    # merged/re-ranked results sent to the local Qwen server

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
AUDIO_PROVIDER = os.getenv("AUDIO_PROVIDER", "pyttsx3").lower()

# ── OCR ───────────────────────────────────────────────────────────────────────
TESSERACT_LANG = "eng+hin+mar"
OCR_MIN_CHARS  = 50   # if PyMuPDF returns fewer chars, fall back to OCR
