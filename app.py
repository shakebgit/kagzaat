"""
app.py — Kagazat Entry Point
Creates the Flask app, wires extensions, registers blueprints.
No business logic lives here.
"""

import logging
import os
import resend
from flask import Flask, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from config.settings import (
    SECRET_KEY, DEBUG, IS_PRODUCTION,
    ALLOWED_ORIGINS, DATABASE_URL, DB_MIN_CONN, DB_MAX_CONN,
    RESEND_API_KEY, REDIS_URL, FRONTEND_FOLDER,
)
from extensions.db import init_pool
from extensions.limiter import limiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__, static_folder="frontend", static_url_path="")
    app.config["SECRET_KEY"] = SECRET_KEY

    # ── Resend ────────────────────────────────────────────────
    resend.api_key = RESEND_API_KEY

    # ── CORS ──────────────────────────────────────────────────
    CORS(
        app,
        resources={
            r"/*": {
                "origins":             ALLOWED_ORIGINS,
                "methods":             ["GET", "POST", "PUT", "OPTIONS"],
                "allow_headers":       ["Content-Type"],
                "expose_headers":      ["Set-Cookie"],
                "supports_credentials": True,
            }
        },
    )

    # ── Rate limiter (init BEFORE blueprints) ─────────────────
    limiter.storage_uri = REDIS_URL
    limiter.init_app(app)

    # ── Security headers ──────────────────────────────────────
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"]        = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.tailwindcss.com https://fonts.googleapis.com 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com;"
        )
        return response

    # ── Global error handler ──────────────────────────────────
     
    

    @app.errorhandler(Exception)
    def handle_error(e):
        if isinstance(e, HTTPException):
            return e   # ✅ let Flask handle 404, 405, etc.

        logger.error("Unhandled exception: %s", e)
        return {"status": "error", "message": "Internal server error"}, 500

    # ── Blueprints ────────────────────────────────────────────
    from routes.auth       import auth_bp
    from routes.password   import password_bp
    from routes.profile    import profile_bp
    from routes.documents  import documents_bp
    from routes.contact    import contact_bp
    from routes.location   import location_bp
    from routes.lookup     import lookup_bp
    from routes.template   import template_bp
    from routes.affidavit  import affidavit_bp

    for bp in [
        auth_bp, password_bp, profile_bp, documents_bp, contact_bp,
        location_bp, lookup_bp, template_bp, affidavit_bp,
    ]:
        app.register_blueprint(bp)

    # ── Health check ──────────────────────────────────────────
    @app.route("/health")
    def health():
        from extensions.db import is_pool_ready
        return {"status": "alive", "db": "ready" if is_pool_ready() else "not ready"}

    # ── Static file serving ───────────────────────────────────
    @app.route("/")
    def serve_index():
        return send_from_directory(FRONTEND_FOLDER, "index.html")

    @app.route("/<path:filename>")
    def serve_file(filename):
        return send_from_directory(FRONTEND_FOLDER, filename)

    return app


# ── DB pool init ──────────────────────────────────────────────
try:
    init_pool(DATABASE_URL, DB_MIN_CONN, DB_MAX_CONN)
except Exception as e:
    logger.warning("DB pool init failed at startup: %s — routes will 503 until DB is available", e)

app = create_app()

if __name__ == "__main__":
    app.run(debug=DEBUG, port=5000)
