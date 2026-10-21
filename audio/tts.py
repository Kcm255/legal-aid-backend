"""
audio/tts.py — Text-to-Speech using gTTS (Google Text-to-Speech, free, no API key).

Generates MP3 files and saves them to the AUDIO_DIR.
"""
import uuid
from pathlib import Path
from gtts import gTTS
from config import AUDIO_DIR, GTTS_LANG_MAP


def generate_audio(text: str, language: str = "en") -> str:
    """
    Generate an MP3 audio file from text using gTTS.

    Args:
        text: The text to convert to speech.
        language: Language code ('en', 'hi', 'mr').

    Returns:
        Filename (not full path) of the generated MP3 file.

    Raises:
        RuntimeError: If gTTS fails (e.g., no internet connection).
    """
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    lang_code = GTTS_LANG_MAP.get(language, "en")
    
    filename = f"audio_{uuid.uuid4().hex[:12]}.mp3"
    output_path = AUDIO_DIR / filename

    try:
        tts = gTTS(text=text, lang=lang_code, slow=False)
        tts.save(str(output_path))
    except Exception as e:
        raise RuntimeError(f"gTTS failed: {e}. Check internet connection.")

    return filename


def build_audio_text(summary: dict, language: str = "en") -> str:
    """
    Build a human-readable audio script from a summary dict.
    Flattens the structured summary into a speakable paragraph.
    """
    parts = []
    
    doc_type = summary.get("document_type", "")
    if doc_type:
        parts.append(f"This document is a {doc_type}.")
    
    s = summary.get("summary", {})
    if s.get("what_it_is"):
        parts.append(s["what_it_is"])
    if s.get("what_it_means"):
        parts.append(s["what_it_means"])
    if s.get("what_to_do"):
        parts.append(f"What you should do: {s['what_to_do']}")

    disclaimer = (
        "Please note: This is an AI-generated summary for informational purposes only "
        "and is not legal advice. Please consult a qualified lawyer for guidance."
    )
    parts.append(disclaimer)
    
    return " ".join(parts)
