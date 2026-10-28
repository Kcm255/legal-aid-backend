"""Offline-first text-to-speech for generated legal summaries."""
import uuid
import re
from config import AUDIO_DIR, AUDIO_PROVIDER, GTTS_LANG_MAP


def generate_audio(text: str, language: str = "en") -> str:
    """
    Generate a local WAV file using Windows SAPI through pyttsx3.

    Args:
        text: The text to convert to speech.
        language: Language code ('en', 'hi', 'mr').

    Returns:
        Filename (not full path) of the generated WAV file.

    Raises:
        RuntimeError: If the local Windows speech engine is unavailable.
    """
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    lang_code = GTTS_LANG_MAP.get(language, "en")
    
    if AUDIO_PROVIDER != "pyttsx3":
        raise RuntimeError(f"Unsupported offline audio provider: {AUDIO_PROVIDER}")

    try:
        import pyttsx3
    except ImportError as exc:
        raise RuntimeError("Install pyttsx3 to enable offline audio generation.") from exc

    filename = f"audio_{uuid.uuid4().hex[:12]}.wav"
    output_path = AUDIO_DIR / filename

    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 155)
        voices = engine.getProperty("voices") or []
        wanted = lang_code.lower()
        for voice in voices:
            metadata = f"{voice.id} {voice.name} {voice.languages}".lower()
            if wanted in metadata:
                engine.setProperty("voice", voice.id)
                break
        engine.save_to_file(text, str(output_path))
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        output_path.unlink(missing_ok=True)
        raise RuntimeError(f"Offline speech generation failed: {e}") from e

    if not output_path.exists() or output_path.stat().st_size == 0:
        output_path.unlink(missing_ok=True)
        raise RuntimeError("Offline speech engine did not create an audio file.")

    return filename


def build_audio_text(summary: dict, language: str = "en") -> str:
    """
    Build a human-readable audio script from a summary dict.
    Flattens the structured summary into a speakable paragraph.
    """
    localized = {
        "en": {
            "intro": "This document is about",
            "meaning": "In simple terms",
            "action": "The most important next step is",
            "disclaimer": "This is an AI-generated explanation for information only, not legal advice. Please consult a qualified lawyer for advice about your situation.",
        },
        "hi": {
            "intro": "यह दस्तावेज़ इस विषय में है",
            "meaning": "सरल शब्दों में इसका अर्थ है",
            "action": "सबसे महत्वपूर्ण अगला कदम है",
            "disclaimer": "यह केवल जानकारी के लिए एआई द्वारा तैयार की गई व्याख्या है, कानूनी सलाह नहीं। अपनी स्थिति के लिए योग्य वकील से सलाह लें।",
        },
        "mr": {
            "intro": "हा दस्तऐवज या विषयाबद्दल आहे",
            "meaning": "सोप्या शब्दांत याचा अर्थ असा आहे",
            "action": "सर्वात महत्त्वाची पुढील पायरी म्हणजे",
            "disclaimer": "ही केवळ माहितीसाठी एआयने तयार केलेली माहिती आहे, कायदेशीर सल्ला नाही. आपल्या परिस्थितीसाठी पात्र वकिलांचा सल्ला घ्या.",
        },
    }.get(language, None) or {
        "intro": "This document is about",
        "meaning": "In simple terms",
        "action": "The most important next step is",
        "disclaimer": "This is an AI-generated explanation for information only, not legal advice.",
    }

    parts = []
    doc_type = summary.get("document_type", "")
    if doc_type:
        parts.append(f"{localized['intro']} {doc_type}.")
    
    s = summary.get("summary", {}) or {}
    if s.get("what_it_is"):
        parts.append(str(s["what_it_is"]).strip())
    if s.get("what_it_means"):
        parts.append(f"{localized['meaning']}: {str(s['what_it_means']).strip()}")
    if s.get("what_to_do"):
        action = s["what_to_do"]
        if isinstance(action, list):
            actions = [str(item).strip() for item in action if str(item).strip()]
        else:
            actions = [item.strip() for item in re.split(r"(?:\r?\n|(?=\d+\.\s))", str(action)) if item.strip()]
        # Remove list numbering so TTS does not awkwardly read item numbers.
        actions = [re.sub(r"^\s*\d+[.)]\s*", "", item) for item in actions]
        action_text = ". ".join(actions[:4]).strip(" .")
        if action_text:
            parts.append(f"{localized['action']}: {action_text}.")

    parts.append(localized["disclaimer"])
    
    return " ".join(parts)
