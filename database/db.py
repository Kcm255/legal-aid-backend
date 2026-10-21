"""
database/db.py — SQLite setup with WAL mode.

Tables:
  sessions    — simple session IDs (no auth)
  jobs        — async processing jobs (upload → OCR → RAG → Gemini → audio)
  summaries   — cached Gemini summaries keyed by content hash
  chat_history — per-session Q&A history
"""
import sqlite3
import hashlib
import threading
from pathlib import Path
from config import SQLITE_PATH

_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """Return a thread-local SQLite connection with WAL mode and row factory."""
    if not hasattr(_local, "conn") or _local.conn is None:
        SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(SQLITE_PATH), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return _local.conn


def init_db() -> None:
    """Create all tables if they do not already exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            language    TEXT NOT NULL DEFAULT 'en'
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id           TEXT PRIMARY KEY,
            session_id   TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'pending',
            filename     TEXT,
            file_path    TEXT,
            language     TEXT NOT NULL DEFAULT 'en',
            result_json  TEXT,
            error_msg    TEXT,
            created_at   TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS summaries (
            content_hash TEXT PRIMARY KEY,
            language     TEXT NOT NULL,
            summary_json TEXT NOT NULL,
            created_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT NOT NULL,
            job_id      TEXT NOT NULL,
            role        TEXT NOT NULL,
            message     TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );
    """)
    conn.commit()


def compute_content_hash(text: str, language: str) -> str:
    """SHA-256 hash of extracted text + language, used as cache key."""
    return hashlib.sha256(f"{language}::{text}".encode()).hexdigest()


def get_cached_summary(content_hash: str):
    """Return cached summary dict or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT summary_json FROM summaries WHERE content_hash = ?",
        (content_hash,)
    ).fetchone()
    if row:
        import json
        return json.loads(row["summary_json"])
    return None


def cache_summary(content_hash: str, language: str, summary: dict) -> None:
    """Persist a summary to the cache table."""
    import json
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO summaries (content_hash, language, summary_json)
           VALUES (?, ?, ?)""",
        (content_hash, language, json.dumps(summary, ensure_ascii=False))
    )
    conn.commit()
