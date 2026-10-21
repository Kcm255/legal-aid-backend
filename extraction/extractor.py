"""
extraction/extractor.py — Orchestrates text extraction.

Priority:
  1. PyMuPDF text layer (fast, no compute needed)
  2. OCR fallback (OpenCV → PyTesseract) if text is absent or garbled
"""
from pathlib import Path
from .pdf_extractor import extract_text_pymupdf, is_text_sufficient
from .ocr_extractor import extract_text_from_image, extract_text_from_pdf_ocr


def extract_text(file_path: str | Path) -> dict:
    """
    Extract text from a PDF or image file.

    Returns:
        {
          "text": str,
          "method": "pymupdf" | "ocr_pdf" | "ocr_image",
          "error": str | None
        }
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()
    result = {"text": "", "method": None, "error": None}

    if suffix == ".pdf":
        # Step 1: try PyMuPDF text layer
        text = extract_text_pymupdf(file_path)
        if is_text_sufficient(text):
            result["text"] = text
            result["method"] = "pymupdf"
            return result

        # Step 2: fall back to OCR
        print(f"[extractor] PyMuPDF returned insufficient text ({len(text)} chars), falling back to OCR.")
        try:
            text = extract_text_from_pdf_ocr(file_path)
            result["text"] = text
            result["method"] = "ocr_pdf"
        except Exception as e:
            result["error"] = f"OCR failed: {str(e)}"

    elif suffix == ".txt":
        try:
            result["text"] = file_path.read_text(encoding="utf-8")
            result["method"] = "text"
        except UnicodeDecodeError:
            result["error"] = "Text file must be UTF-8 encoded."

    elif suffix in {".jpg", ".jpeg", ".png"}:
        try:
            text = extract_text_from_image(file_path)
            result["text"] = text
            result["method"] = "ocr_image"
        except Exception as e:
            result["error"] = f"Image OCR failed: {str(e)}"
    else:
        result["error"] = f"Unsupported file type: {suffix}"

    return result
