"""
app.py — Flask application factory for Rural Legal Aid Summarizer.
"""
import re
from flask import Flask
from flask_cors import CORS
from config import MAX_CONTENT_LENGTH, UPLOAD_DIR, AUDIO_DIR, CHROMA_DIR
from database.db import init_db

def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

    # Enable CORS for the frontend dev servers AND Chrome Extensions
    CORS(app, resources={r"/api/*": {"origins": [
        "http://localhost:5173",   # Vite dev server (FRONTEND)
        "http://localhost:5174",   # Vite fallback when 5173 is occupied
        "http://localhost:3000",   # CRA / alternative
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "https://legal-aid-amber.vercel.app",
        re.compile(r"chrome-extension://.*") # Allows requests from your browser extension
    ]}})

    # Ensure required directories exist
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize SQLite (WAL mode, create tables)
    with app.app_context():
        init_db()

    # Register blueprints
    from routes.upload import upload_bp
    from routes.status import status_bp
    from routes.chat import chat_bp
    from routes.audio import audio_bp
    from routes.session import session_bp
    from routes.translate import translate_bp

    app.register_blueprint(upload_bp)
    app.register_blueprint(status_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(audio_bp)
    app.register_blueprint(session_bp)
    app.register_blueprint(translate_bp)

    # Root redirection/message
    @app.route("/")
    def index():
        return {
            "status": "ok",
            "message": "Rural Legal Aid Summarizer API is running.",
            "frontend_url": "http://localhost:5173"
        }

    # Health check
    @app.route("/api/health")
    def health():
        return {"status": "ok", "app": "Rural Legal Aid Summarizer"}

    # User-facing error handlers
    @app.errorhandler(413)
    def file_too_large(e):
        return {"error": "File is too large. Maximum allowed size is 16 MB."}, 413

    @app.errorhandler(404)
    def not_found(e):
        return {"error": "Endpoint not found."}, 404

    @app.errorhandler(500)
    def internal_error(e):
        return {"error": "Internal server error. Please try again."}, 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)