"""
ai/processor.py — Orchestrates the full document processing pipeline.

Pipeline:
  1. Extract text (PyMuPDF / OCR)
  2. Check SQLite cache (skip Qwen if already processed)
  3. RAG: retrieve relevant legal context
  4. Qwen: summarize + extract dates/amounts + translate
  5. Offline Windows speech: generate audio
  6. Store in SQLite, update job status
"""
import json
import traceback
from pathlib import Path
from database.db import (
    get_connection, compute_content_hash,
    get_cached_summary, cache_summary
)
from extraction.extractor import extract_text
from rag.retrieve import get_context_chunks
from ai.llm import call_llm_json, call_llm
from ai.prompts import (
    get_summary_prompt,
    get_translation_prompt,
    get_followup_prompt,
    LEGAL_DISCLAIMER,
)
from audio.tts import generate_audio, build_audio_text


def extract_amounts_from_text(text: str) -> list[dict]:
    """Recover currency values and classify them from nearby document wording."""
    import re
    pattern = re.compile(
        r"(?i)(?:₹|rs\.?|inr\.?|rupees?)\s*[\d][\d,]*(?:\.\d{1,2})?\s*(?:/-)?"
        r"|\b[\d][\d,]*(?:\.\d{1,2})?\s*(?:rupees?|rs\.?|/-)"
    )
    amounts, seen = [], set()
    for match in pattern.finditer(text or ""):
        value = re.sub(r"\s+", " ", match.group(0)).strip()
        if value.lower() in seen:
            continue
        seen.add(value.lower())
        context_start = max(0, match.start() - 140)
        context = text[context_start:match.end() + 80]
        label = classify_amount_context(context, match.start() - context_start)
        amounts.append({"label": label, "value": value})
        if len(amounts) == 5:
            break
    return amounts


def classify_amount_context(context: str, amount_position: int | None = None) -> str:
    """Return a specific user-facing label from the amount's nearby text."""
    context_lower = context.casefold()
    labels = (
        (("repair", "maintenance", "मरम्मत"), "Repair / Maintenance Amount"),
        (("rent", "किराया"), "Rent Amount"),
        (("principal", "मूलधन"), "Principal Amount"),
        (("outstanding", "payable", "balance", "due", "बकाया", "देय"), "Outstanding / Due Amount"),
        (("total dues", "total amount", "grand total", "कुल राशि"), "Total Amount Due"),
        (("fine", "penalty", "दंड", "जुर्माना"), "Fine / Penalty Amount"),
        (("interest", "ब्याज"), "Interest Amount"),
        (("emi", "installment", "instalment", "किस्त"), "Monthly EMI"),
        (("court fee", "filing fee", "न्यायालय शुल्क"), "Court / Filing Fee"),
        (("stamp duty", "स्टाम्प शुल्क"), "Stamp Duty"),
        (("legal charge", "legal fee", "विधिक शुल्क"), "Legal Charges"),
        (("security deposit", "जमानत राशि"), "Security Deposit"),
        (("compensation", "damages", "मुआवजा", "क्षतिपूर्ति"), "Compensation / Damages"),
    )
    closest_label = "Document Amount"
    closest_distance = len(context_lower) + 1
    if amount_position is None:
        amount_position = len(context_lower) // 2
    preceding_matches = []
    following_matches = []
    for keywords, label in labels:
        for keyword in keywords:
            position = context_lower.find(keyword)
            if position >= 0:
                distance = amount_position - position
                if distance >= 0:
                    preceding_matches.append((distance, label))
                else:
                    following_matches.append((-distance, label))
    candidates = preceding_matches or following_matches
    if candidates:
        closest_label = min(candidates, key=lambda match: match[0])[1]
    return closest_label


def normalize_extracted_amounts(summary: dict, extracted_text: str) -> dict:
    """Drop malformed amounts and replace vague labels using document context."""
    import re

    currency_value = re.compile(
        r"(?i)(?:₹|rs\.?|inr\.?|rupees?)?\s*[\d][\d,]*(?:\.\d{1,2})?"
    )
    generic_labels = {"", "amount", "rs", "inr", "rupees", "money"}
    normalized = []

    for item in summary.get("extracted_amounts", []):
        if isinstance(item, str):
            label, value = "", item
        elif isinstance(item, dict):
            label = str(item.get("label") or "").strip()
            value = str(item.get("value") or "").strip()
        else:
            continue

        if not value or not currency_value.search(value):
            continue

        context = ""
        number_match = re.search(r"[\d][\d,]*(?:\.\d{1,2})?", value)
        if number_match:
            number = re.escape(number_match.group(0))
            source_match = re.search(number, extracted_text or "")
            if source_match:
                context_start = max(0, source_match.start() - 140)
                context = extracted_text[context_start:source_match.end() + 80]
                amount_position = source_match.start() - context_start
            else:
                amount_position = None
        else:
            amount_position = None

        if label.casefold() in generic_labels:
            label = classify_amount_context(context, amount_position)
        normalized.append({
            "label": label or classify_amount_context(context, amount_position),
            "value": value,
        })

    summary["extracted_amounts"] = normalized[:5]
    return summary


def ensure_extracted_amounts(summary: dict, extracted_text: str) -> dict:
    """Validate model output and recover missing amounts from document text."""
    if not isinstance(summary.get("extracted_amounts"), list):
        summary["extracted_amounts"] = []
    normalize_extracted_amounts(summary, extracted_text)
    if not summary["extracted_amounts"]:
        summary["extracted_amounts"] = extract_amounts_from_text(extracted_text)
    return summary


def _has_selected_language(text: str, language: str) -> bool:
    """Check that translated user-facing text contains the requested script."""
    if language == "en":
        return True
    # Hindi and Marathi both use Devanagari.
    return any("\u0900" <= char <= "\u097f" for char in text)


def _translate_value_plain(value: object, language: str) -> object:
    """Translate one summary value without relying on fragile JSON output."""
    if not value:
        return value
    language_name = {"hi": "Hindi", "mr": "Marathi"}[language]
    prompt = f"""
Translate the following legal-summary text into {language_name}.
Use Devanagari script. Return only the translation, with no explanation,
quotation marks, JSON, or English sentences. Preserve names, dates, amounts,
and legal terms accurately.

TEXT:
{value}
"""
    return call_llm(prompt, use_reasoning=False).strip()


def update_job(
    job_id: str,
    status: str,
    result: dict | None = None,
    error: str | None = None,
):
    conn = get_connection()
    if result is not None:
        conn.execute(
            """UPDATE jobs SET status=?, result_json=?, updated_at=datetime('now') WHERE id=?""",
            (status, json.dumps(result, ensure_ascii=False), job_id)
        )
    elif error is not None:
        conn.execute(
            """UPDATE jobs SET status=?, error_msg=?, updated_at=datetime('now') WHERE id=?""",
            (status, error, job_id)
        )
    else:
        conn.execute(
            """UPDATE jobs SET status=?, updated_at=datetime('now') WHERE id=?""",
            (status, job_id)
        )
    conn.commit()


def get_job(job_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row:
        return dict(row)
    return None


def process_document(job_id: str, file_path: str, language: str = "en"):
    """
    Full async pipeline. Called in a background thread.
    Updates job status in SQLite throughout.
    """
    try:
        update_job(job_id, "extracting")

        # ── Step 1: Extract text ──────────────────────────────────────────────
        extraction = extract_text(file_path)
        if extraction["error"]:
            update_job(job_id, "error", error=f"Text extraction failed: {extraction['error']}")
            return

        extracted_text = extraction["text"]
        if not extracted_text.strip():
            update_job(job_id, "error", error="Could not extract any text from this document. "
                       "Please ensure the document is legible.")
            return

        # ── Step 2: Check cache ───────────────────────────────────────────────
        content_hash = compute_content_hash(extracted_text, language)
        cached = get_cached_summary(content_hash)
        if cached:
            print(f"[processor] Cache hit for job {job_id}")
            ensure_extracted_amounts(cached, extracted_text)
            update_job(job_id, "done", result=cached)
            return

        update_job(job_id, "retrieving_context")

        # ── Step 3: RAG retrieval ─────────────────────────────────────────────
        context_chunks = get_context_chunks(extracted_text[:1500])

        update_job(job_id, "generating_summary")

        # ── Step 4: Qwen summarization ────────────────────────────────────────
        summary_prompt = get_summary_prompt(extracted_text[:4000], context_chunks[:3], language)
        summary = call_llm_json(summary_prompt, use_reasoning=False)

        # Qwen can occasionally return English despite the requested language.
        # Translate the user-facing fields server-side before audio is created,
        # so both the page and narration always use the selected language.
        if language != "en":
            translatable = {
                "document_type": summary.get("document_type", ""),
                "summary": summary.get("summary", {}),
            }
            translation_prompt = get_translation_prompt(
                json.dumps(translatable, ensure_ascii=False), language
            )
            translated = None
            for attempt in range(2):
                try:
                    retry_suffix = ""
                    if attempt:
                        retry_suffix = (
                            f"\n\nCRITICAL: Return one complete valid JSON object in {language}. "
                            "Use Devanagari text and do not echo English sentences."
                        )
                    candidate = call_llm_json(
                        translation_prompt + retry_suffix,
                        use_reasoning=False,
                    )
                    if _has_selected_language(
                        json.dumps(candidate, ensure_ascii=False), language
                    ):
                        translated = candidate
                        break
                except RuntimeError as exc:
                    print(f"[processor] Translation attempt {attempt + 1} failed: {exc}")

            if translated:
                summary["document_type"] = translated.get(
                    "document_type", summary.get("document_type", "")
                )
                summary["summary"] = translated.get(
                    "summary", summary.get("summary", {})
                )
            else:
                # Retry field-by-field as plain text. This avoids malformed JSON
                # responses and guarantees the audio source is translated too.
                try:
                    summary["document_type"] = _translate_value_plain(
                        summary.get("document_type", ""), language
                    )
                    original_summary = summary.get("summary", {}) or {}
                    translated_summary = {}
                    for field in ("what_it_is", "what_it_means", "what_to_do"):
                        translated_summary[field] = _translate_value_plain(
                            original_summary.get(field, ""), language
                        )
                    summary["summary"] = translated_summary
                except Exception as exc:
                    # Keep the original valid summary and continue processing;
                    # an optional translation failure must not break the job.
                    print(f"[processor] Plain translation unavailable: {exc}")
        ensure_extracted_amounts(summary, extracted_text)

        # Add extraction metadata and store extracted text for follow-up Q&A
        summary["extraction_method"] = extraction["method"]
        summary["language"] = language
        summary["_extracted_text"] = extracted_text  # used by follow-up chat

        update_job(job_id, "generating_audio")

        # ── Step 5: Offline audio ──────────────────────────────────────────────
        # Build narration only from the verified summary. Do not send a second
        # free-form request to Qwen: it can produce a short or unrelated script
        # that mentions arbitrary numbers instead of explaining the document.
        audio_text = build_audio_text(summary, language)
        print(f"[processor] Audio narration prepared: {len(audio_text)} characters ({language})")
        summary["audio_script"] = audio_text
        try:
            audio_filename = generate_audio(audio_text, language)
            summary["audio_filename"] = audio_filename
        except Exception as e:
            print(f"[processor] Audio generation failed: {e}")
            summary["audio_filename"] = None
            summary["audio_error"] = str(e)

        # Add disclaimer
        summary["disclaimer"] = LEGAL_DISCLAIMER.strip()

        # ── Step 6: Cache and finish ──────────────────────────────────────────
        cache_summary(content_hash, language, summary)
        update_job(job_id, "done", result=summary)
        print(f"[processor] Job {job_id} completed successfully.")

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        print(f"[processor] Job {job_id} failed: {error_msg}")
        traceback.print_exc()
        update_job(job_id, "error", error=error_msg)


def answer_followup(question: str, job_id: str, session_id: str, language: str = "en") -> str:
    """
    Answer a follow-up question grounded in the original document and RAG context.
    Saves Q&A to chat_history table.
    """
    conn = get_connection()
    
    # Get original document text
    job = get_job(job_id)
    original_text = ""
    if job and job.get("result_json"):
        result = json.loads(job["result_json"])
        original_text = result.get("_extracted_text", "")

    # Get file path for re-extraction if needed
    if not original_text and job and job.get("file_path"):
        extraction = extract_text(job["file_path"])
        original_text = extraction.get("text", "")

    # RAG retrieval for the question
    context_chunks = get_context_chunks(question)

    # Chat history
    history_rows = conn.execute(
        """SELECT role, message FROM chat_history 
           WHERE session_id=? AND job_id=? ORDER BY id DESC LIMIT 10""",
        (session_id, job_id)
    ).fetchall()
    chat_history = [{"role": r["role"], "message": r["message"]} for r in reversed(history_rows)]

    # Local/remote Qwen
    prompt = get_followup_prompt(question, context_chunks, original_text, chat_history, language)
    answer = call_llm(prompt, use_reasoning=True)

    # Store in history
    conn.execute(
        "INSERT INTO chat_history (session_id, job_id, role, message) VALUES (?,?,?,?)",
        (session_id, job_id, "user", question)
    )
    conn.execute(
        "INSERT INTO chat_history (session_id, job_id, role, message) VALUES (?,?,?,?)",
        (session_id, job_id, "assistant", answer)
    )
    conn.commit()
    return answer
