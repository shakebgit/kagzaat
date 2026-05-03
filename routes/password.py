"""
routes/password.py — Password Reset Flow
forgot_password → verify_otp → reset_password
"""

import secrets
import jwt
from datetime import datetime, timedelta
from flask import Blueprint, request, current_app

from extensions.db import get_db_connection
from extensions.limiter import limiter
from helpers.validators import validate_email, validate_password
from helpers.sanitizers import sanitize_input
from helpers.responses import ok, fail
from helpers.email import send_otp_email
from middleware.auth import write_audit

password_bp = Blueprint("password", __name__)


def _generate_otp() -> str:
    return "".join([str(secrets.randbelow(10)) for _ in range(6)])


@password_bp.route("/forgot-password", methods=["POST"])
@limiter.limit("3 per 10 minutes")
def forgot_password():
    try:
        data  = request.json or {}
        email = sanitize_input(data.get("email", ""))

        if not validate_email(email):
            return fail("Invalid email format")

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM userdetails WHERE email = %s AND is_active = TRUE",
                (email,),
            )
            user = cur.fetchone()

            if user:
                otp_code  = _generate_otp()
                user_name = user["name"] or "User"

                cur.execute(
                    "UPDATE password_reset_otp SET is_used = TRUE WHERE user_email = %s AND is_used = FALSE",
                    (email,),
                )
                cur.execute(
                    """
                    INSERT INTO password_reset_otp (user_email, otp_code, expires_at)
                    VALUES (%s, %s, NOW() + INTERVAL '15 minutes')
                    """,
                    (email, otp_code),
                )
                write_audit(cur, email, "OTP_REQUESTED")
                send_otp_email(email, user_name, otp_code)

        # Always return success — don't reveal if email exists
        return ok(message="If this email is registered, an OTP has been sent.")

    except Exception as e:
        current_app.logger.error("Forgot password error: %s", e)
        return fail("Server error", 500)


@password_bp.route("/verify-otp", methods=["POST"])
@limiter.limit("10 per minute")
def verify_otp():
    try:
        data  = request.json or {}
        email = sanitize_input(data.get("email", ""))
        otp   = sanitize_input(data.get("otp", ""))

        if not validate_email(email) or not otp:
            return fail("Invalid request")

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, otp_code, expires_at, attempts, is_used
                FROM   password_reset_otp
                WHERE  user_email = %s AND is_used = FALSE
                ORDER  BY created_at DESC LIMIT 1
                """,
                (email,),
            )
            row = cur.fetchone()

            if not row:
                return fail("No active OTP found. Please request a new one.")

            otp_id     = row["id"]
            stored_otp = row["otp_code"]
            expires_at = row["expires_at"]
            attempts   = row["attempts"]

            if datetime.utcnow().replace(tzinfo=expires_at.tzinfo) > expires_at:
                cur.execute("UPDATE password_reset_otp SET is_used=TRUE WHERE id=%s", (otp_id,))
                return fail("OTP has expired. Please request a new one.")

            if attempts >= 5:
                cur.execute("UPDATE password_reset_otp SET is_used=TRUE WHERE id=%s", (otp_id,))
                return fail("Too many attempts. Please request a new OTP.", 429)

            if otp != stored_otp:
                cur.execute(
                    "UPDATE password_reset_otp SET attempts = attempts + 1 WHERE id = %s",
                    (otp_id,),
                )
                remaining = 4 - attempts
                return fail(f"Incorrect OTP. {remaining} attempt(s) remaining.")

            cur.execute("UPDATE password_reset_otp SET is_used = TRUE WHERE id = %s", (otp_id,))
            write_audit(cur, email, "OTP_VERIFIED")

        reset_token = jwt.encode(
            {
                "email":   email,
                "purpose": "password_reset",
                "exp":     datetime.utcnow() + timedelta(minutes=5),
            },
            current_app.config["SECRET_KEY"],
            algorithm="HS256",
        )

        return ok(data={"reset_token": reset_token})

    except Exception as e:
        current_app.logger.error("Verify OTP error: %s", e)
        return fail("Server error", 500)


@password_bp.route("/reset-password", methods=["POST"])
@limiter.limit("5 per minute")
def reset_password():
    try:
        data             = request.json or {}
        reset_token      = data.get("reset_token", "")
        new_password     = data.get("new_password", "")
        confirm_password = data.get("confirm_password", "")

        try:
            payload = jwt.decode(
                reset_token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            if payload.get("purpose") != "password_reset":
                raise ValueError("Invalid token purpose")
            email = payload["email"]
        except jwt.ExpiredSignatureError:
            return fail("Reset session expired. Please start again.")
        except Exception:
            return fail("Invalid reset token.")

        if new_password != confirm_password:
            return fail("Passwords do not match.")

        is_valid, msg = validate_password(new_password)
        if not is_valid:
            return fail(msg)

        from werkzeug.security import generate_password_hash
        hashed = generate_password_hash(new_password, method="pbkdf2:sha256")

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE userdetails SET password = %s WHERE email = %s",
                (hashed, email),
            )
            if cur.rowcount == 0:
                return fail("User not found.", 404)
            write_audit(cur, email, "PASSWORD_RESET")

        return ok(message="Password reset successfully. Please log in.")

    except Exception as e:
        current_app.logger.error("Reset password error: %s", e)
        return fail("Server error", 500)
