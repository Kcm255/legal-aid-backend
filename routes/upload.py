"""
routes/upload.py — POST /api/upload
Accepts PDF/JPG/PNG, validates, saves, enqueues background processing job.
"""
import uuid
import threading
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from config import UPLOAD_DIR, ALLOWED_EXTENSIONS
from database.db import get_connection
from ai.processor import process_document

upload_bp = Blueprint("upload", __name__)


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@upload_bp.route("/api/upload", methods=["POST"])
def upload_document():
    # Validate session
    session_id = request.form.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    language = request.form.get("language", "en")
    if language not in ["en", "hi", "mr"]:
        language = "en"

    # Validate file
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Please select a PDF or image."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    if not allowed_file(file.filename):
        return jsonify({
            "error": f"Unsupported file type. Please upload PDF, JPG, or PNG files only."
        }), 400

    # Save file
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = secure_filename(file.filename)
    job_id = uuid.uuid4().hex
    # Prefix with job_id to avoid collisions
    saved_filename = f"{job_id}_{filename}"
    file_path = UPLOAD_DIR / saved_filename
    file.save(str(file_path))

    # Create session if it doesn't exist
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO sessions (id, language) VALUES (?, ?)",
        (session_id, language)
    )
    
    # Create job record
    conn.execute(
        """INSERT INTO jobs (id, session_id, status, filename, file_path, language)
           VALUES (?, ?, 'pending', ?, ?, ?)""",
        (job_id, session_id, filename, str(file_path), language)
    )
    conn.commit()

    # Launch background processing thread
    thread = threading.Thread(
        target=process_document,
        args=(job_id, str(file_path), language),
        daemon=True,
        name=f"process-{job_id[:8]}"
    )
    thread.start()

    return jsonify({
        "job_id": job_id,
        "status": "pending",
        "filename": filename,
        "message": "Document uploaded. Processing started."
    }), 202
