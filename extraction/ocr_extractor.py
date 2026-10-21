"""
extraction/ocr_extractor.py — OCR pipeline for scanned PDFs and images.

Pipeline:
  PDF → pdf2image → [OpenCV preprocessing] → PyTesseract
  Image (JPG/PNG) → [OpenCV preprocessing] → PyTesseract

OpenCV preprocessing steps:
  1. Resize to at least 1000px on the long side (better OCR accuracy)
  2. Convert to grayscale
  3. Denoise (fastNlMeansDenoising)
  4. Adaptive threshold (binarize)
  5. Deskew (find and correct rotation)

Language packs: tries eng+hin+mar first; falls back to eng-only if
Hindi/Marathi packs are not installed on this machine.
"""
import cv2  # type: ignore
import numpy as np  # type: ignore
import pytesseract  # type: ignore
from PIL import Image  # type: ignore
from pathlib import Path

try:
    from pdf2image import convert_from_path  # type: ignore
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

from config import TESSERACT_LANG


def _get_available_lang() -> str:
    """
    Return the best available Tesseract language string.
    Falls back to 'eng' if Hindi/Marathi packs are not installed,
    so the app still works without the extra language packs.
    """
    try:
        available = pytesseract.get_languages(config="")
        parts = [l for l in TESSERACT_LANG.split("+") if l in available]
        if not parts:
            return "eng"
        return "+".join(parts)
    except Exception:
        return "eng"


# Cache the resolved language string so we only check once
_RESOLVED_LANG: str | None = None


def get_tesseract_lang() -> str:
    global _RESOLVED_LANG
    if _RESOLVED_LANG is None:
        _RESOLVED_LANG = _get_available_lang()
        if _RESOLVED_LANG != TESSERACT_LANG:
            print(
                f"[OCR] Warning: Some language packs not found. "
                f"Using lang='{_RESOLVED_LANG}' instead of '{TESSERACT_LANG}'.\n"
                f"      To enable Hindi/Marathi OCR, install Tesseract language packs:\n"
                f"      Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
                f"      Linux:   sudo apt install tesseract-ocr-hin tesseract-ocr-mar"
            )
    return _RESOLVED_LANG


def _resize_for_ocr(img: np.ndarray) -> np.ndarray:
    """Upscale image if it's smaller than 1000px on the long side."""
    h, w = img.shape[:2]
    if max(h, w) < 1000:
        scale = 1000 / max(h, w)
        img = cv2.resize(
            img, (int(w * scale), int(h * scale)),
            interpolation=cv2.INTER_CUBIC
        )
    return img


def _deskew(img: np.ndarray) -> np.ndarray:
    """Detect and correct rotation up to ±45 degrees."""
    try:
        coords = np.column_stack(np.where(img > 0))
        if len(coords) < 10:
            return img
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) < 0.5:
            return img
        h, w = img.shape
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            img, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
        return rotated
    except Exception:
        return img


def preprocess_image(img: np.ndarray) -> np.ndarray:
    """Apply full preprocessing pipeline to a BGR image array."""
    img = _resize_for_ocr(img)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    binary = cv2.adaptiveThreshold(
        denoised, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )
    deskewed = _deskew(binary)
    return deskewed


def ocr_image_array(img_array: np.ndarray) -> str:
    """Run PyTesseract on a preprocessed numpy image array."""
    processed = preprocess_image(img_array)
    pil_img = Image.fromarray(processed)
    lang = get_tesseract_lang()
    config = "--oem 3 --psm 6"
    text = pytesseract.image_to_string(pil_img, lang=lang, config=config)
    return text.strip()


def extract_text_from_image(file_path: str | Path) -> str:
    """OCR a JPG/PNG image file."""
    img = cv2.imread(str(file_path))
    if img is None:
        raise ValueError(f"Cannot read image: {file_path}")
    return ocr_image_array(img)


def extract_text_from_pdf_ocr(file_path: str | Path) -> str:
    """
    Convert PDF pages to images (via pdf2image/Poppler) and OCR each page.
    Returns concatenated text from all pages.
    """
    if not PDF2IMAGE_AVAILABLE:
        raise ImportError(
            "pdf2image is not installed. Install it with: pip install pdf2image\n"
            "Also install Poppler:\n"
            "  Linux:   sudo apt install poppler-utils\n"
            "  Windows: https://github.com/oschwartz10612/poppler-windows/releases\n"
            "  macOS:   brew install poppler"
        )
    pages = convert_from_path(str(file_path), dpi=200)
    text_parts = []
    for page_img in pages:
        img_array = np.array(page_img.convert("RGB"))
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        text_parts.append(ocr_image_array(img_bgr))
    return "\n\n".join(text_parts)
