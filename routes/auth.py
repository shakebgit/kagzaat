"""
routes/auth.py — Authentication Routes
login, register, logout, check_auth
"""

import jwt
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, make_response, current_app
from werkzeug.security import generate_password_hash, check_password_hash

from extensions.db import get_db_connection
from extensions.limiter import limiter
from helpers.validators import validate_email, validate_password, validate_mobile
from helpers.sanitizers import sanitize_input
from helpers.responses import ok, fail
from middleware.auth import require_auth, write_audit
from config.settings import IS_PRODUCTION

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    try:
        data     = request.json or {}
        email    = sanitize_input(data.get("email"))
        password = data.get("password", "")

        if not validate_email(email):
            return fail("Invalid email format")

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT userid, email, password, name FROM userdetails WHERE email = %s AND is_active = TRUE",
                (email,),
            )
            user = cur.fetchone()

            if not user or not check_password_hash(user["password"], password):
                return fail("Invalid credentials", 401)

            cur.execute(
                "UPDATE userdetails SET last_login_at = NOW() WHERE email = %s", (email,)
            )
            write_audit(cur, email, "LOGIN")

        token = jwt.encode(
            {
                "sub":   str(user["userid"]),
                "email": email,
                "name":  user["name"] or "",
                "exp":   datetime.utcnow() + timedelta(hours=24),
            },
            current_app.config["SECRET_KEY"],
            algorithm="HS256",
        )

        response = make_response(ok(message="Login successful"))
        response.set_cookie(
            "session_token",
            token,
            httponly=True,
            secure=IS_PRODUCTION,
            samesite="Lax",
            max_age=86400,
        )
        return response

    except Exception as e:
        current_app.logger.error("Login error: %s", e)
        return fail("Server error", 500)


@auth_bp.route("/register", methods=["POST"])
@limiter.limit("3 per hour")
def register():
    try:
        data     = request.json or {}
        name     = sanitize_input(data.get("name"))
        address  = sanitize_input(data.get("address"))
        city     = sanitize_input(data.get("city"))
        country  = sanitize_input(data.get("country", "India"))
        email    = sanitize_input(data.get("email"))
        password = data.get("password", "")
        mobile   = sanitize_input(data.get("mobile", ""))

        if not validate_email(email):
            return fail("Invalid email format")

        is_valid, msg = validate_password(password)
        if not is_valid:
            return fail(msg)

        if mobile and not validate_mobile(mobile):
            return fail("Invalid mobile number")

        hashed = generate_password_hash(password, method="pbkdf2:sha256")

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT email FROM userdetails WHERE email = %s", (email,))
            if cur.fetchone():
                return fail("Email already registered", 409)

            cur.execute(
                """
                INSERT INTO userdetails (name, address, city, country, email, password, mobile)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (name, address, city, country, email, hashed, mobile or None),
            )
            write_audit(cur, email, "REGISTER")

        return ok(message="User registered successfully"), 201

    except Exception as e:
        current_app.logger.error("Register error: %s", e)
        return fail("Registration failed. Please try again.", 500)


@auth_bp.route("/check-auth", methods=["GET"])
@require_auth
def check_auth():
     return ok(data={
        "status": "authenticated",
        "id":    request.user_id,
        "email": request.user_email,
        "name":  request.user_name,
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():
    response = make_response(jsonify({"status": "success", "message": "Logged out"}))
    response.set_cookie("session_token", "", expires=0)
    return response
