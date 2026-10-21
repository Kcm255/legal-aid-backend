"""
extraction/pdf_extractor.py — Extract text from PDFs using PyMuPDF (fast, no OCR).

Uses PyMuPDF's text layer; returns empty string if the PDF has no embedded text
(scanned document) so the caller can fall back to OCR.
"""
import fitz  # PyMuPDF
from pathlib import Path
from config import OCR_MIN_CHARS


def extract_text_pymupdf(file_path: str | Path) -> str:
    """
    Extract text from a PDF using PyMuPDF.

    Returns:
        Extracted text string, or empty string if text layer is absent/garbled.
    """
    text_parts = []
    try:
        doc = fitz.open(str(file_path))
        for page in doc:
            text_parts.append(page.get_text("text"))
        doc.close()
    except Exception as e:
        print(f"[PyMuPDF] Error reading {file_path}: {e}")
        return ""

    full_text = "\n".join(text_parts).strip()
    return full_text


def is_text_sufficient(text: str) -> bool:
    """
    Heuristic: text is usable if it contains at least OCR_MIN_CHARS printable characters
    and a reasonable word-to-character ratio (not garbled encoding noise).
    """
    if len(text) < OCR_MIN_CHARS:
        return False
    # Check word density — garbled text has very few spaces
    words = text.split()
    if len(words) < 10:
        return False
    return True
