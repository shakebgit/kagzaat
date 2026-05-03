"""
routes/profile.py — User Profile Routes
get_profile, update_profile, change_password
"""

from flask import Blueprint, request, make_response, current_app
from werkzeug.security import generate_password_hash, check_password_hash

from extensions.db import get_db_connection
from extensions.limiter import limiter
from helpers.validators import validate_password, validate_mobile
from helpers.sanitizers import sanitize_input
from helpers.responses import ok, fail
from middleware.auth import require_auth, write_audit

profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/get-profile", methods=["GET"])
@require_auth
def get_profile():
    try:
        print (request.user_email)
        email = request.user_email

        with get_db_connection() as conn:
           with   conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    ud.email,
                    ud.name        AS auth_name,
                    up.display_name,
                    COALESCE(up.mobile, ud.mobile) AS mobile,
                    up.address,
                    up.city,
                    up.state,
                    up.country,
                    up.pincode,
                    up.photo_url,
                    ud.created_at
                FROM userdetails ud
                LEFT JOIN userprofile up ON up.user_email = ud.email
                WHERE ud.email = %s
                """,
                (email,),
            )
            row = cur.fetchone()

        if not row:
            return fail("User not found", 404)
        
        print ( row["email"], row["auth_name"], row["display_name"], row["mobile"], row["address"], row["city"], row["state"], row["country"], row["pincode"], row["photo_url"], row["created_at"] )

        return ok(data={
            "email":         row["email"],
            "name":          row["display_name"] or row["auth_name"] or "",
            "auth_name":     row["auth_name"] or "",
            "mobile":        row["mobile"] or "",
            "address":       row["address"] or "",
            "city":          row["city"] or "",
            "state":         row["state"] or "",
            "country":       row["country"] or "India",
            "pincode":       row["pincode"] or "",
            "photo_url":     row["photo_url"] or "",
            "registered_at": row["created_at"].isoformat() if row["created_at"] else "",
        })

    except Exception as e:
        current_app.logger.error("Get profile error: %s", e)
        return fail("Server error", 500)


@profile_bp.route("/update-profile", methods=["POST"])
@require_auth
@limiter.limit("30 per hour")
def update_profile():
    try:
        data    = request.json or {}
        email   = request.user_email
        name    = sanitize_input(data.get("name", ""))
        mobile  = sanitize_input(data.get("mobile", ""))
        address = sanitize_input(data.get("address", ""))
        city    = sanitize_input(data.get("city", ""))
        state   = sanitize_input(data.get("state", ""))
        country = sanitize_input(data.get("country", "India"))
        pincode = sanitize_input(data.get("pincode", ""))

        if not name:
            return fail("Name is required.")

        if mobile and not validate_mobile(mobile):
            return fail("Invalid mobile number.")

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO userprofile
                    (user_email, display_name, mobile, address, city, state, country, pincode)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_email) DO UPDATE
                    SET display_name = EXCLUDED.display_name,
                        mobile       = EXCLUDED.mobile,
                        address      = EXCLUDED.address,
                        city         = EXCLUDED.city,
                        state        = EXCLUDED.state,
                        country      = EXCLUDED.country,
                        pincode      = EXCLUDED.pincode,
                        updated_at   = NOW()
                """,
                (email, name, mobile or None, address, city, state, country, pincode or None),
            )
            cur.execute(
                "UPDATE userdetails SET name = %s WHERE email = %s", (name, email)
            )
            write_audit(cur, email, "PROFILE_UPDATED", {
                "fields": ["name", "mobile", "address", "city", "state", "country", "pincode"]
            })

        return ok(message="Profile updated successfully.")

    except Exception as e:
        current_app.logger.error("Update profile error: %s", e)
        return fail("Server error", 500)


@profile_bp.route("/change-password", methods=["POST"])
@require_auth
@limiter.limit("5 per minute")
def change_password():
    try:
        data             = request.json or {}
        email            = request.user_email
        current_password = data.get("current_password", "")
        new_password     = data.get("new_password", "")
        confirm_password = data.get("confirm_password", "")

        if new_password != confirm_password:
            return fail("Passwords do not match.")

        is_valid, msg = validate_password(new_password)
        if not is_valid:
            return fail(msg)

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT password FROM userdetails WHERE email = %s", (email,))
            row = cur.fetchone()

            if not row or not check_password_hash(row["password"], current_password):
                return fail("Current password is incorrect.", 401)

            if check_password_hash(row["password"], new_password):
                return fail("New password must differ from current password.")

            hashed = generate_password_hash(new_password, method="pbkdf2:sha256")
            cur.execute(
                "UPDATE userdetails SET password = %s WHERE email = %s", (hashed, email)
            )
            write_audit(cur, email, "PASSWORD_CHANGED")

        response = make_response(ok(message="Password changed. Please log in again."))
        response.set_cookie("session_token", "", expires=0)
        return response

    except Exception as e:
        current_app.logger.error("Change password error: %s", e)
        return fail("Server error", 500)
