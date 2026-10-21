"""
routes/status.py — GET /api/status/<job_id>
Returns current job status and result when done.
"""
import json
from flask import Blueprint, jsonify
from database.db import get_connection

status_bp = Blueprint("status", __name__)


@status_bp.route("/api/status/<job_id>", methods=["GET"])
def get_status(job_id: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    
    if not row:
        return jsonify({"error": "Job not found"}), 404

    job = dict(row)
    response = {
        "job_id": job_id,
        "status": job["status"],
        "filename": job["filename"],
        "language": job["language"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
    }

    # Status labels for UI
    status_messages = {
        "pending":            "Waiting to start…",
        "extracting":         "Extracting text from document…",
        "ocr":                "Running OCR on document…",
        "retrieving_context": "Retrieving legal context…",
        "generating_summary": "Generating AI summary…",
        "generating_audio":   "Generating audio…",
        "done":               "Complete!",
        "error":              "Processing failed.",
    }
    response["status_message"] = status_messages.get(job["status"], job["status"])

    if job["status"] == "done" and job["result_json"]:
        response["result"] = json.loads(job["result_json"])

    if job["status"] == "error" and job["error_msg"]:
        response["error"] = job["error_msg"]

    return jsonify(response)
