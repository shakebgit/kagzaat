"""
auth_middleware.py — JWT httpOnly cookie guard
"""

import jwt
from functools import wraps
from flask import current_app, request, jsonify, g


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = request.cookies.get("session_token")

        if not token:
            return jsonify({"error": "Unauthorized"}), 401

        try:
            payload = jwt.decode(
                token,
                current_app.config["SECRET_KEY"],
                algorithms=["HS256"]
            )

            g.user_id = payload.get("sub")  #or payload.get("user_id")
            g.user_name = payload.get("name", "")

        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Session expired"}), 401

        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return fn(*args, **kwargs)

    return wrapper