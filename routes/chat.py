"""
routes/chat.py — POST /api/chat
Follow-up Q&A grounded in retrieved legal context and original document.
"""
from flask import Blueprint, request, jsonify
from ai.processor import answer_followup

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    question = data.get("question", "").strip()
    job_id = data.get("job_id", "").strip()
    session_id = data.get("session_id", "").strip()
    language = data.get("language", "en")

    if not question:
        return jsonify({"error": "Question cannot be empty"}), 400
    if not job_id:
        return jsonify({"error": "job_id is required"}), 400
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    if language not in ["en", "hi", "mr"]:
        language = "en"

    try:
        answer = answer_followup(question, job_id, session_id, language)
        return jsonify({"answer": answer, "question": question})
    except RuntimeError as e:
        error_msg = str(e)
        # User-friendly rate limit message
        if "rate limit" in error_msg.lower() or "429" in error_msg:
            return jsonify({
                "error": "The AI service is temporarily busy (rate limit reached). "
                         "Please wait a minute and try again."
            }), 429
        return jsonify({"error": error_msg}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500
