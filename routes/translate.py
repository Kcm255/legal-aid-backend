"""
routes/translate.py — POST /api/translate
Translates the summary portion of an existing job's result into a target language.
Only summary.what_it_is / what_it_means / what_to_do / document_type are translated.
Dates, amounts, audio, and internal fields are passed through unchanged.
"""
import json
from flask import Blueprint, request, jsonify
from database.db import get_connection
from ai.llm import call_llm_json
from ai.prompts import get_translation_prompt

translate_bp = Blueprint("translate", __name__)


@translate_bp.route("/api/translate", methods=["POST"])
def translate_summary():
    data = request.get_json(force=True, silent=True) or {}
    job_id   = data.get("job_id")
    language = data.get("language", "en")

    if not job_id:
        return jsonify({"error": "job_id is required"}), 400

    if language == "en":
        # English is the original — just return the stored result
        conn = get_connection()
        row = conn.execute("SELECT result_json FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row or not row["result_json"]:
            return jsonify({"error": "Job not found or not complete"}), 404
        return jsonify({"result": json.loads(row["result_json"])})

    # Fetch the stored (English) result
    conn = get_connection()
    row = conn.execute("SELECT result_json FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row or not row["result_json"]:
        return jsonify({"error": "Job not found or not complete"}), 404

    original = json.loads(row["result_json"])

    # Build a slim payload — only the fields we want translated
    translatable = {
        "document_type": original.get("document_type", ""),
        "summary": original.get("summary", {}),
    }

    try:
        prompt = get_translation_prompt(json.dumps(translatable, ensure_ascii=False), language)
        translated = call_llm_json(prompt, use_reasoning=False)
    except Exception as e:
        return jsonify({"error": f"Translation failed: {str(e)}"}), 500

    # Merge translated fields back into original (keep dates, amounts, audio, etc.)
    merged = dict(original)
    merged["document_type"] = translated.get("document_type", original.get("document_type", ""))
    merged["summary"] = translated.get("summary", original.get("summary", {}))
    merged["language"] = language

    return jsonify({"result": merged})
