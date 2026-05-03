"""
middleware/auth.py — Authentication Decorator + Audit Logger
Import require_auth into any route that needs a logged-in user.
"""

import json
import logging
import jwt
from functools import wraps
from flask import request, jsonify, current_app

logger = logging.getLogger(__name__)


def require_auth(f):
    """
    Validates JWT from httpOnly cookie.
    Sets request.user_id, request.user_email, request.user_name on success.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("session_token")
        if not token:
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        try:
            data = jwt.decode(
                token,
                current_app.config["SECRET_KEY"],
                algorithms=["HS256"],
            )
            request.user_id    = data.get("sub", "")
            request.user_email = data["email"]
            request.user_name  = data.get("name", "")
        except jwt.ExpiredSignatureError:
            return jsonify({"status": "error", "message": "Session expired — please log in again"}), 401
        except Exception:
            return jsonify({"status": "error", "message": "Invalid session token"}), 401
        return f(*args, **kwargs)
    return decorated


# ── Alias for blueprints that use the old name ─────────────────
# affidavit.py and template.py import login_required from auth_middleware.
# After restructuring they import from middleware.auth.
# This alias means zero changes needed in those files.
login_required = require_auth


def write_audit(cursor, user_email: str, action: str, meta: dict = None):
    """
    Inserts a row into audit_log.
    Must be called inside an active get_db_connection() block.
    """
    ip = request.remote_addr
    ua = request.headers.get("User-Agent", "")
    try:
        cursor.execute(
            """
            INSERT INTO audit_log (user_email, action, ip_address, user_agent, meta)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_email, action, ip, ua, json.dumps(meta) if meta else None),
        )
    except Exception as e:
        logger.warning("Audit log write failed: %s", e)
        # Never raise — audit failure must not break the user request
