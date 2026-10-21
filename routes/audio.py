"""
routes/audio.py — GET /api/audio/<filename>
Serves generated MP3 audio files.
"""
from flask import Blueprint, send_from_directory, jsonify
from config import AUDIO_DIR

audio_bp = Blueprint("audio", __name__)


@audio_bp.route("/api/audio/<filename>", methods=["GET"])
def serve_audio(filename: str):
    # Basic security: disallow path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Invalid filename"}), 400
    
    audio_path = AUDIO_DIR / filename
    if not audio_path.exists():
        return jsonify({"error": "Audio file not found"}), 404

    return send_from_directory(str(AUDIO_DIR), filename, mimetype="audio/mpeg")
