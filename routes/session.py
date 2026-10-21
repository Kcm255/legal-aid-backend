"""
routes/session.py — POST /api/session
Create or resume a session (no auth — simple UUID-based sessions).
"""
import uuid
from flask import Blueprint, request, jsonify
from database.db import get_connection

session_bp = Blueprint("session", __name__)


@session_bp.route("/api/session", methods=["POST"])
def create_session():
    data = request.get_json() or {}
    existing_id = data.get("session_id")
    language = data.get("language", "en")
    if language not in ["en", "hi", "mr"]:
        language = "en"

    conn = get_connection()

    if existing_id:
        # Try to resume existing session
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (existing_id,)).fetchone()
        if row:
            return jsonify({
                "session_id": existing_id,
                "language": row["language"],
                "resumed": True,
            })

    # Create new session
    session_id = uuid.uuid4().hex
    conn.execute("INSERT INTO sessions (id, language) VALUES (?, ?)", (session_id, language))
    conn.commit()

    return jsonify({
        "session_id": session_id,
        "language": language,
        "resumed": False,
    })


@session_bp.route("/api/session/<session_id>/history", methods=["GET"])
def get_history(session_id: str):
    """Return the list of jobs for a session."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT id, status, filename, language, created_at 
           FROM jobs WHERE session_id=? ORDER BY created_at DESC LIMIT 20""",
        (session_id,)
    ).fetchall()
    jobs = [dict(r) for r in rows]
    return jsonify({"jobs": jobs})
