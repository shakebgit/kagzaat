"""
config/settings.py — Kagazat Configuration
All environment variables read once here. Nothing else calls os.getenv().
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Flask ─────────────────────────────────────────────────────
SECRET_KEY   = os.getenv("SECRET_KEY", "change-me-in-production")
DEBUG        = os.getenv("DEBUG", "False") == "True"
FLASK_ENV    = os.getenv("FLASK_ENV", "development")
IS_PRODUCTION = FLASK_ENV == "production"

# ── Database ──────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")
DB_MIN_CONN  = int(os.getenv("DB_MIN_CONN", "1"))
DB_MAX_CONN  = int(os.getenv("DB_MAX_CONN", "20"))

# ── Rate limiting ─────────────────────────────────────────────
# Use Redis in production (set REDIS_URL in Railway), memory in dev
REDIS_URL = os.getenv("REDIS_URL", "memory://")

# ── Email ─────────────────────────────────────────────────────
RESEND_API_KEY   = os.getenv("RESEND_API_KEY")
FROM_EMAIL       = "helpdesk@kagazat.in"
CONTACT_RECIPIENT = os.getenv("CONTACT_EMAIL", "helpdesk@kagazat.in")

# ── CORS ─────────────────────────────────────────────────────
ALLOWED_ORIGINS = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://127.0.0.1:5000",
    "https://kagazat.in",
    "https://www.kagazat.in",
    "https://kagzaat-production.up.railway.app",
]

# ── Storage ───────────────────────────────────────────────────
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "downloads")
FRONTEND_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
