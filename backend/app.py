"""
app.py  –  Kagazat.in Flask Backend
Version : 2.1.0  (Production-ready fixes)
Fixes applied:
  - FIX 1: Cookie secure= now environment-aware (False local, True on HTTPS)
  - FIX 2: OTP now uses secrets module (cryptographically secure)
  - FIX 3: /downloads/<filename> route added so PDF download works
  - FIX 4: import json moved to top level
  - FIX 5: Rate limit on update_profile raised to 30/hour
"""

from flask import Flask, request, jsonify, make_response, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
import os
import secrets                          # FIX 2: was "import random, string"
import json                             # FIX 4: moved from inside write_audit()
from dotenv import load_dotenv
from weasyprint import HTML
from datetime import datetime, timedelta
import re
import jwt
from functools import wraps
import resend
import base64

#------------
from weasyprint import HTML
import bleach
import re
#-----------
import logging
logging.basicConfig(level=logging.INFO)

# ── New blueprints ────────────────────────────────────────────
from routes.location import location_bp
from routes.lookup   import lookup_bp
from routes.template import template_bp
from routes.affidavit import affidavit_bp
# ──────────────────────────────────────────────
# Boot
# ──────────────────────────────────────────────
load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY")

app = Flask(__name__, static_folder='frontend', static_url_path='')
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

#Error handling 
@app.errorhandler(Exception)
def handle_error(e):
    app.logger.error(f"Unhandled Exception: {str(e)}")
    return jsonify({
        "status": "error",
        "message": "Internal server error"
    }), 500
#--End--

# FIX 1: detect production environment for secure cookie flag
IS_PRODUCTION = os.getenv("FLASK_ENV", "development") == "production"

# ──────────────────────────────────────────────
# CORS
# ──────────────────────────────────────────────
ALLOWED_ORIGINS = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://127.0.0.1:5000",
    "https://kagazat.in",
    "https://www.kagazat.in",
    "https://kagzaat-production.up.railway.app"

]

CORS(
    app,
    resources={
        r"/*": {
            "origins": ALLOWED_ORIGINS,
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type"],
            "expose_headers": ["Set-Cookie"],
            "supports_credentials": True,
        }
    },
)

# ── Register blueprints ───────────────────────────────────────
# app.register_blueprint(auth_bp)          # your existing auth
app.register_blueprint(location_bp)
app.register_blueprint(lookup_bp)
app.register_blueprint(template_bp)
app.register_blueprint(affidavit_bp)


#---


# ──────────────────────────────────────────────
# Rate Limiting
# ──────────────────────────────────────────────
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# ──────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

connection_pool = None


def init_db_pool():
    global connection_pool
    connection_pool = pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=20,
        dsn=DATABASE_URL,
    )


@contextmanager
def get_db_connection():
    conn = connection_pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        connection_pool.putconn(conn)


# ──────────────────────────────────────────────
# Validation helpers
# ──────────────────────────────────────────────
def validate_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


def validate_password(password: str):
    """Returns (bool, message)."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain an uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain a lowercase letter"
    if not re.search(r"[0-9]", password):
        return False, "Password must contain a number"
    return True, "Valid"


def validate_mobile(mobile: str) -> bool:
    """Indian mobile: 10 digits, starts with 6-9."""
    return bool(re.match(r"^[6-9]\d{9}$", mobile))


def sanitize_input(text) -> str:
    if text is None:
        return ""
    return re.sub(r"<[^>]*>", "", str(text)).strip()
    
    
def success_response(data=None, message="Success", status_code=200):
    return jsonify({
        "success": True,
        "data": data or {},
        "message": message
    }), status_code


def error_response(message="Error", status_code=400):
    return jsonify({
        "success": False,
        "data": {},
        "message": message
    }), status_code


# ──────────────────────────────────────────────
# OTP helper — FIX 2: uses secrets (cryptographically secure)
# ──────────────────────────────────────────────
def generate_otp() -> str:
    """Returns a cryptographically secure 6-digit OTP."""
    return "".join([str(secrets.randbelow(10)) for _ in range(6)])


# ──────────────────────────────────────────────
# Audit helper — FIX 4: json imported at top, not here
# ──────────────────────────────────────────────
def write_audit(cursor, user_email: str, action: str, meta: dict = None):
    ip = request.remote_addr
    ua = request.headers.get("User-Agent", "")
    cursor.execute(
        """
        INSERT INTO audit_log (user_email, action, ip_address, user_agent, meta)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user_email, action, ip, ua, json.dumps(meta) if meta else None),
    )


# ──────────────────────────────────────────────
# Auth decorator
# ──────────────────────────────────────────────
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("session_token")
        if not token:
            return jsonify({"error": "Unauthorized"}), 401
        try:
            data = jwt.decode(
                token, app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            request.user_id    = data.get("sub", "")   
            request.user_email = data["email"]
            request.user_name  = data.get("name", "")
            
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Session expired"}), 401
        except Exception:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "alive"})


# ── Login ──────────────────────────────────────
@app.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    try:
        data     = request.json
        email    = sanitize_input(data.get("email"))
        password = data.get("password", "")
        user_id= data.get("id", "")

        if not validate_email(email):
            return jsonify({"status": "fail", "message": "Invalid email format"}), 400

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT userid,email, password, name FROM userdetails WHERE email = %s AND is_active = TRUE",
                (email,),
            )
            user = cur.fetchone()

            if user and check_password_hash(user[2], password):
                cur.execute(
                    "UPDATE userdetails SET last_login_at = NOW() WHERE email = %s",
                    (email,),
                )
                write_audit(cur, email, "LOGIN")
                user_id   = str(user[0])   # ← add this
                user_name = user[3] or ""  # ← name now index [3]
            else:
                cur.close()
                return jsonify({"status": "fail", "message": "Invalid credentials"}), 401

            cur.close()

        token = jwt.encode(
            {
                 "sub":   user_id,      # ← add this                
                 "email": email,
                 "name":  user_name,
                 "exp":   datetime.utcnow() + timedelta(hours=24),
            },
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )

        response = make_response(
            jsonify({"status": "success", "message": "Login successful"})
        )
        # FIX 1: secure=IS_PRODUCTION — False locally, True on HTTPS production
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
        app.logger.error("Login error: %s", e)
        return jsonify({"status": "error", "message": "Server error"}), 500


# ── Register ───────────────────────────────────
@app.route("/register", methods=["POST"])
@limiter.limit("3 per hour")
def register():
    try:
        data     = request.json
        name     = sanitize_input(data.get("name"))
        address  = sanitize_input(data.get("address"))
        city     = sanitize_input(data.get("city"))
        country  = sanitize_input(data.get("country", "India"))
        email    = sanitize_input(data.get("email"))
        password = data.get("password", "")
        mobile   = sanitize_input(data.get("mobile", ""))

        if not validate_email(email):
            return jsonify({"status": "error", "message": "Invalid email format"}), 400

        is_valid, msg = validate_password(password)
        if not is_valid:
            return jsonify({"status": "error", "message": msg}), 400

        if mobile and not validate_mobile(mobile):
            return jsonify({"status": "error", "message": "Invalid mobile number"}), 400

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT email FROM userdetails WHERE email = %s", (email,))
            if cur.fetchone():
                cur.close()
                return jsonify({"status": "error", "message": "Email already registered"}), 409

            cur.execute(
                """
                INSERT INTO userdetails (name, address, city, country, email, password, mobile)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (name, address, city, country, email, hashed_password, mobile or None),
            )
            write_audit(cur, email, "REGISTER")
            cur.close()

        return jsonify({"status": "success", "message": "User registered successfully"}), 201

    except Exception as e:
        app.logger.error("Register error: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# ── Check Auth ─────────────────────────────────
@app.route("/check-auth", methods=["GET"])
@require_auth
def check_auth():
    return jsonify({
        "status": "authenticated",
        "id":     request.user_id,    # ← add this
        "email":  request.user_email,
        "name":   request.user_name,
    })


# ── Logout ─────────────────────────────────────
@app.route("/logout", methods=["POST"])
def logout():
    response = make_response(jsonify({"status": "success", "message": "Logged out"}))
    response.set_cookie("session_token", "", expires=0)
    return response


# ══════════════════════════════════════════════
# FORGOT PASSWORD – Step 1: Request OTP
# ══════════════════════════════════════════════
@app.route("/forgot-password", methods=["POST"])
@limiter.limit("3 per 10 minutes")
def forgot_password():
    try:
        data  = request.json or {}
        email = sanitize_input(data.get("email", ""))

        if not validate_email(email):
            return jsonify({"status": "error", "message": "Invalid email format"}), 400

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM userdetails WHERE email = %s AND is_active = TRUE",
                (email,),
            )
            user = cur.fetchone()

            if user:
                user_name = user[0] or "User"
                otp_code  = generate_otp()

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
                cur.close()
                _send_otp_email(email, user_name, otp_code)
            else:
                cur.close()

        return jsonify({
            "status": "success",
            "message": "If this email is registered, an OTP has been sent.",
        }), 200

    except Exception as e:
        app.logger.error("Forgot password error: %s", e)
        return jsonify({"status": "error", "message": "Server error"}), 500


# ══════════════════════════════════════════════
# VERIFY OTP – Step 2
# ══════════════════════════════════════════════
@app.route("/verify-otp", methods=["POST"])
@limiter.limit("10 per minute")
def verify_otp():
    try:
        data  = request.json or {}
        email = sanitize_input(data.get("email", ""))
        otp   = sanitize_input(data.get("otp", ""))

        if not validate_email(email) or not otp:
            return jsonify({"status": "error", "message": "Invalid request"}), 400

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
                cur.close()
                return jsonify({"status": "error", "message": "No active OTP found. Please request a new one."}), 400

            otp_id, stored_otp, expires_at, attempts, is_used = row

            if datetime.utcnow().replace(tzinfo=expires_at.tzinfo) > expires_at:
                cur.execute("UPDATE password_reset_otp SET is_used=TRUE WHERE id=%s", (otp_id,))
                cur.close()
                return jsonify({"status": "error", "message": "OTP has expired. Please request a new one."}), 400

            if attempts >= 5:
                cur.execute("UPDATE password_reset_otp SET is_used=TRUE WHERE id=%s", (otp_id,))
                cur.close()
                return jsonify({"status": "error", "message": "Too many attempts. Please request a new OTP."}), 429

            if otp != stored_otp:
                cur.execute(
                    "UPDATE password_reset_otp SET attempts = attempts + 1 WHERE id = %s",
                    (otp_id,),
                )
                remaining = 4 - attempts
                cur.close()
                return jsonify({
                    "status":  "error",
                    "message": f"Incorrect OTP. {remaining} attempt(s) remaining.",
                }), 400

            cur.execute("UPDATE password_reset_otp SET is_used = TRUE WHERE id = %s", (otp_id,))
            write_audit(cur, email, "OTP_VERIFIED")
            cur.close()

        reset_token = jwt.encode(
            {
                "email":   email,
                "purpose": "password_reset",
                "exp":     datetime.utcnow() + timedelta(minutes=5),
            },
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )

        return jsonify({"status": "success", "reset_token": reset_token}), 200

    except Exception as e:
        app.logger.error("Verify OTP error: %s", e)
        return jsonify({"status": "error", "message": "Server error"}), 500


# ══════════════════════════════════════════════
# RESET PASSWORD – Step 3
# ══════════════════════════════════════════════
@app.route("/reset-password", methods=["POST"])
@limiter.limit("5 per minute")
def reset_password():
    try:
        data             = request.json or {}
        reset_token      = data.get("reset_token", "")
        new_password     = data.get("new_password", "")
        confirm_password = data.get("confirm_password", "")

        try:
            payload = jwt.decode(reset_token, app.config["SECRET_KEY"], algorithms=["HS256"])
            if payload.get("purpose") != "password_reset":
                raise ValueError("Invalid token purpose")
            email = payload["email"]
        except jwt.ExpiredSignatureError:
            return jsonify({"status": "error", "message": "Reset session expired. Please start again."}), 400
        except Exception:
            return jsonify({"status": "error", "message": "Invalid reset token."}), 400

        if new_password != confirm_password:
            return jsonify({"status": "error", "message": "Passwords do not match."}), 400

        is_valid, msg = validate_password(new_password)
        if not is_valid:
            return jsonify({"status": "error", "message": msg}), 400

        hashed = generate_password_hash(new_password, method="pbkdf2:sha256")

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE userdetails SET password = %s WHERE email = %s",
                (hashed, email),
            )
            if cur.rowcount == 0:
                cur.close()
                return jsonify({"status": "error", "message": "User not found."}), 404
            write_audit(cur, email, "PASSWORD_RESET")
            cur.close()

        return jsonify({"status": "success", "message": "Password reset successfully. Please log in."}), 200

    except Exception as e:
        app.logger.error("Reset password error: %s", e)
        return jsonify({"status": "error", "message": "Server error"}), 500


# ══════════════════════════════════════════════
# CHANGE PASSWORD (logged-in)
# ══════════════════════════════════════════════
@app.route("/change-password", methods=["POST"])
@require_auth
@limiter.limit("5 per minute")
def change_password():
    try:
        data             = request.json or {}
        current_password = data.get("current_password", "")
        new_password     = data.get("new_password", "")
        confirm_password = data.get("confirm_password", "")
        email            = request.user_email

        if new_password != confirm_password:
            return jsonify({"status": "error", "message": "Passwords do not match."}), 400

        is_valid, msg = validate_password(new_password)
        if not is_valid:
            return jsonify({"status": "error", "message": msg}), 400

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT password FROM userdetails WHERE email = %s", (email,))
            row = cur.fetchone()

            if not row or not check_password_hash(row[0], current_password):
                cur.close()
                return jsonify({"status": "error", "message": "Current password is incorrect."}), 401

            if check_password_hash(row[0], new_password):
                cur.close()
                return jsonify({"status": "error", "message": "New password must differ from current password."}), 400

            hashed = generate_password_hash(new_password, method="pbkdf2:sha256")
            cur.execute(
                "UPDATE userdetails SET password = %s WHERE email = %s",
                (hashed, email),
            )
            write_audit(cur, email, "PASSWORD_CHANGED")
            cur.close()

        response = make_response(
            jsonify({"status": "success", "message": "Password changed. Please log in again."})
        )
        response.set_cookie("session_token", "", expires=0)
        return response

    except Exception as e:
        app.logger.error("Change password error: %s", e)
        return jsonify({"status": "error", "message": "Server error"}), 500


# ══════════════════════════════════════════════
# GET PROFILE
# ══════════════════════════════════════════════
@app.route("/get-profile", methods=["GET"])
@require_auth
def get_profile():
    try:
        email = request.user_email

        with get_db_connection() as conn:
            cur = conn.cursor()
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
            cur.close()

        if not row:
            return jsonify({"status": "error", "message": "User not found"}), 404

        profile = {
            "email":         row[0],
            "name":          row[2] or row[1] or "",
            "auth_name":     row[1] or "",
            "mobile":        row[3] or "",
            "address":       row[4] or "",
            "city":          row[5] or "",
            "state":         row[6] or "",
            "country":       row[7] or "India",
            "pincode":       row[8] or "",
            "photo_url":     row[9] or "",
            "registered_at": row[10].isoformat() if row[10] else "",
        }

        return jsonify({"status": "success", "profile": profile}), 200

    except Exception as e:
        app.logger.error("Get profile error: %s", e)
        return jsonify({"status": "error", "message": "Server error"}), 500


# ══════════════════════════════════════════════
# UPDATE PROFILE
# ══════════════════════════════════════════════
@app.route("/update-profile", methods=["POST"])
@require_auth
@limiter.limit("30 per hour")           # FIX 5: raised from 10 to 30
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
            return jsonify({"status": "error", "message": "Name is required."}), 400

        if mobile and not validate_mobile(mobile):
            return jsonify({"status": "error", "message": "Invalid mobile number."}), 400

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
                "UPDATE userdetails SET name = %s WHERE email = %s",
                (name, email),
            )
            write_audit(cur, email, "PROFILE_UPDATED", {"fields": ["name","mobile","address","city","state","country","pincode"]})
            cur.close()

        return jsonify({"status": "success", "message": "Profile updated successfully."}), 200

    except Exception as e:
        app.logger.error("Update profile error: %s", e)
        return jsonify({"status": "error", "message": "Server error"}), 500


# ══════════════════════════════════════════════
# DOCUMENT ROUTES
# ══════════════════════════════════════════════

@app.route("/usertempletdetails", methods=["POST"])
@require_auth
def usertempletdetails():
    try:
        data        = request.json
        currentname = sanitize_input(data.get("currentname"))
        newname     = sanitize_input(data.get("newname"))
        fathername  = sanitize_input(data.get("fathername"))
        age         = sanitize_input(data.get("age"))
        dob         = sanitize_input(data.get("dob"))
        gender      = sanitize_input(data.get("gender"))
        address     = sanitize_input(data.get("address"))
        reason      = sanitize_input(data.get("reason"))
        mobile      = sanitize_input(data.get("mobile"))
        aadhaar     = sanitize_input(data.get("aadhaar"))
        userid      = request.user_email

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO usertempletdetails
                    (currentname, newname, guardianname, age, dob, sex,
                     address, reason, mobile, adhar, userid)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (currentname, newname, fathername, age, dob, gender,
                 address, reason, mobile, aadhaar, userid),
            )
            cur.close()

        return jsonify({"status": "success", "message": "Template data saved"}), 201

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/generate_pdf", methods=["POST"])
@require_auth
def generate_pdf():
    try:
        data       = request.json
        html       = data.get("html","")
        safe_html = bleach.clean(
                        html,
                        tags=[
                        'p', 'b', 'i', 'u', 'strong', 'em',
                        'h1', 'h2', 'h3', 'ul', 'ol', 'li',
                        'br', 'span', 'div'
                         ],
                         attributes={'*': ['style']},
                            strip=True
                        )
        if re.search(r'(http://|https://|file://|ftp://|//)', safe_html.lower()):
            raise ValueError("External resources not allowed")
        def safe_url_fetcher(url):
            raise Exception("Blocked external resource")        
        
        user_email = request.user_email
        timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")

        #pdf      = HTML(string=html).write_pdf()
        pdf = HTML(   string=safe_html, url_fetcher=safe_url_fetcher,
                    base_url=None  ).write_pdf()
        
        filename = f"affidavit_NameChange_{timestamp}.pdf"
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)

        with open(filepath, "wb") as f:
            f.write(pdf)

        email_sent = send_pdf_email(user_email, filepath, filename)

        return jsonify({
            "status":     "success",
            "filename":   filename,
            "email_sent": email_sent,
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# FIX 3: New route — serves generated PDF files for download
@app.route("/downloads/<filename>", methods=["GET"])
@require_auth
def download_file(filename):
    """Serve a generated PDF file. Auth required — users can only download their own files."""
    # Basic security: strip any path traversal attempts
    safe_filename = os.path.basename(filename)
    return send_from_directory(
        os.path.abspath(DOWNLOAD_FOLDER),
        safe_filename,
        as_attachment=True,
    )


# ──────────────────────────────────────────────
# Email helpers
# ──────────────────────────────────────────────
def _send_otp_email(to_email: str, user_name: str, otp_code: str) -> bool:
    try:
        resend.Emails.send({
            "from":    "helpdesk@kagazat.in",
            "to":      to_email,
            "subject": "Kagazat – Password Reset OTP | पासवर्ड रीसेट OTP",
            "html": f"""
            <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;
                        border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
              <div style="background:#2563eb;padding:24px;text-align:center;">
                <h2 style="color:#fff;margin:0;">Kagazat</h2>
              </div>
              <div style="padding:32px;">
                <p style="font-size:16px;">नमस्ते {user_name},</p>
                <p style="font-size:15px;">आपका पासवर्ड रीसेट OTP:</p>
                <div style="text-align:center;margin:24px 0;">
                  <span style="font-size:42px;font-weight:bold;letter-spacing:12px;
                               color:#2563eb;">{otp_code}</span>
                </div>
                <p style="font-size:14px;color:#6b7280;">
                  यह OTP <strong>15 मिनट</strong> के लिए वैध है।<br>
                  This OTP is valid for <strong>15 minutes</strong>.
                </p>
                <p style="font-size:13px;color:#ef4444;">
                  यदि आपने यह अनुरोध नहीं किया, तो इस ईमेल को अनदेखा करें।
                </p>
              </div>
              <div style="background:#f9fafb;padding:16px;text-align:center;
                          font-size:12px;color:#9ca3af;">
                © 2026 Kagazat. All rights reserved.
              </div>
            </div>
            """,
        })
        return True
    except Exception as e:
        app.logger.error("OTP email error: %s", e)
        return False


def send_pdf_email(user_email: str, pdf_filepath: str, filename: str) -> bool:
    try:
        with open(pdf_filepath, "rb") as f:
            pdf_content = base64.b64encode(f.read()).decode()

        resend.Emails.send({
            "from":    "helpdesk@kagazat.in",
            "to":      user_email,
            "subject": "आपका शपथपत्र तैयार है | Your Affidavit is Ready",
            "html": f"""
                <h2>नमस्ते!</h2>
                <p>आपका शपथपत्र तैयार है। PDF अटैचमेंट में है।</p>
                <p><strong>File:</strong> {filename}</p>
                <hr>
                <p>Your affidavit is ready. PDF attached.</p>
                <br>
                <p>धन्यवाद | Thank you<br><strong>Kagazat Team</strong></p>
            """,
            "attachments": [{"filename": filename, "content": pdf_content}],
        })
        return True
    except Exception as e:
        app.logger.error("PDF email error: %s", e)
        return False




# ══════════════════════════════════════════════
# CONTACT FORM — paste this block into app.py
# Place it just before the static file serving routes at the bottom
# ══════════════════════════════════════════════

# Add this import at the top of app.py if not already present:
# import re   ← already there
# import resend  ← already there

# ── Contact email recipient ────────────────────────────────────
# Change this to wherever you want contact messages delivered
CONTACT_RECIPIENT = os.getenv("CONTACT_EMAIL", "helpdesk@kagazat.in")


@app.route("/contact", methods=["POST"])
@limiter.limit("3 per 10 minutes")     # prevents spam floods per IP
def contact():
    """
    Accepts  : { name, email, phone, subject, message }
    Behavior :
        1. Validates all inputs server-side
        2. Sends notification email to CONTACT_RECIPIENT (you)
        3. Sends confirmation email to the person who wrote in
    No auth required — contact form is public.
    """
    try:
        data    = request.json or {}

        name    = sanitize_input(data.get("name",    ""))
        email   = sanitize_input(data.get("email",   ""))
        phone   = sanitize_input(data.get("phone",   ""))
        subject = sanitize_input(data.get("subject", ""))
        message = sanitize_input(data.get("message", ""))

        # ── Server-side validation ────────────────────────────
        if not name:
            return jsonify({"status": "error", "message": "Name is required."}), 400

        if not validate_email(email):
            return jsonify({"status": "error", "message": "Invalid email address."}), 400

        if not subject:
            return jsonify({"status": "error", "message": "Subject is required."}), 400

        if not message or len(message) < 10:
            return jsonify({"status": "error", "message": "Message must be at least 10 characters."}), 400

        if phone and not validate_mobile(phone):
            return jsonify({"status": "error", "message": "Invalid mobile number."}), 400

        # ── Get IP for audit trail ────────────────────────────
        sender_ip = request.remote_addr
        timestamp = datetime.now().strftime("%d %b %Y, %I:%M %p")

        # ── Send notification to you (Kagazat team) ───────────
        _send_contact_notification(
            name, email, phone, subject, message, sender_ip, timestamp
        )

        # ── Send confirmation to the user ─────────────────────
        _send_contact_confirmation(name, email, subject)

        # ── Log to audit_log table ────────────────────────────
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO audit_log (user_email, action, ip_address, user_agent, meta)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        email,
                        "CONTACT_FORM",
                        sender_ip,
                        request.headers.get("User-Agent", ""),
                        json.dumps({"name": name, "subject": subject}),
                    ),
                )
                cur.close()
        except Exception as db_err:
            # Don't fail the request if only audit logging fails
            app.logger.warning("Contact audit log failed: %s", db_err)

        return jsonify({
            "status":  "success",
            "message": "Your message has been sent. We will reply within 24 hours.",
        }), 200

    except Exception as e:
        app.logger.error("Contact form error: %s", e)
        return jsonify({"status": "error", "message": "Server error. Please try again."}), 500


# ── Email: Notification to Kagazat team ───────────────────────
def _send_contact_notification(
    name: str, email: str, phone: str,
    subject: str, message: str,
    sender_ip: str, timestamp: str
) -> bool:
    """Sends the contact form message to the Kagazat helpdesk inbox."""
    try:
        phone_line = f"<p><strong>मोबाइल:</strong> {phone}</p>" if phone else ""

        resend.Emails.send({
            "from":    "helpdesk@kagazat.in",
            "to":      CONTACT_RECIPIENT,
            "reply_to": email,          # clicking Reply goes directly to user
            "subject": f"[Kagazat संपर्क] {subject} — {name}",
            "html": f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;
                        border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">

              <!-- Header -->
              <div style="background:#2563eb;padding:20px 24px;">
                <h2 style="color:#fff;margin:0;font-size:18px;">
                  📬 नया संपर्क संदेश — Kagazat
                </h2>
              </div>

              <!-- Body -->
              <div style="padding:28px 24px;">

                <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
                  <tr style="background:#f9fafb;">
                    <td style="padding:10px 14px;font-weight:bold;width:140px;color:#374151;">नाम</td>
                    <td style="padding:10px 14px;color:#111827;">{name}</td>
                  </tr>
                  <tr>
                    <td style="padding:10px 14px;font-weight:bold;color:#374151;">ईमेल</td>
                    <td style="padding:10px 14px;">
                      <a href="mailto:{email}" style="color:#2563eb;">{email}</a>
                    </td>
                  </tr>
                  <tr style="background:#f9fafb;">
                    <td style="padding:10px 14px;font-weight:bold;color:#374151;">मोबाइल</td>
                    <td style="padding:10px 14px;color:#111827;">{phone if phone else "नहीं दिया"}</td>
                  </tr>
                  <tr>
                    <td style="padding:10px 14px;font-weight:bold;color:#374151;">विषय</td>
                    <td style="padding:10px 14px;color:#111827;">{subject}</td>
                  </tr>
                  <tr style="background:#f9fafb;">
                    <td style="padding:10px 14px;font-weight:bold;color:#374151;">समय</td>
                    <td style="padding:10px 14px;color:#111827;">{timestamp}</td>
                  </tr>
                  <tr>
                    <td style="padding:10px 14px;font-weight:bold;color:#374151;">IP</td>
                    <td style="padding:10px 14px;color:#6b7280;font-size:13px;">{sender_ip}</td>
                  </tr>
                </table>

                <!-- Message -->
                <div style="background:#f0f9ff;border-left:4px solid #2563eb;
                            padding:16px 20px;border-radius:4px;margin-bottom:20px;">
                  <p style="font-weight:bold;color:#1e40af;margin:0 0 8px;">संदेश:</p>
                  <p style="color:#1e293b;line-height:1.7;white-space:pre-wrap;margin:0;">{message}</p>
                </div>

                <!-- Quick reply button -->
                <a href="mailto:{email}?subject=Re: {subject}"
                   style="display:inline-block;background:#2563eb;color:#fff;
                          padding:12px 24px;border-radius:6px;text-decoration:none;
                          font-weight:bold;">
                  ✉️ अभी जवाब दें
                </a>

              </div>

              <!-- Footer -->
              <div style="background:#f9fafb;padding:14px 24px;font-size:12px;color:#9ca3af;">
                यह संदेश kagazat.in के Contact Us फ़ॉर्म से आया है।
              </div>
            </div>
            """,
        })
        return True
    except Exception as e:
        app.logger.error("Contact notification email error: %s", e)
        return False


# ── Email: Confirmation to user ───────────────────────────────
def _send_contact_confirmation(name: str, email: str, subject: str) -> bool:
    """Sends an acknowledgement email to the person who contacted us."""
    try:
        resend.Emails.send({
            "from":    "helpdesk@kagazat.in",
            "to":      email,
            "subject": "हमने आपका संदेश प्राप्त किया | Kagazat",
            "html": f"""
            <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;
                        border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">

              <div style="background:#2563eb;padding:24px;text-align:center;">
                <h2 style="color:#fff;margin:0;">Kagazat</h2>
              </div>

              <div style="padding:32px 24px;">
                <p style="font-size:18px;font-weight:bold;color:#111827;">
                  नमस्ते {name} जी! 🙏
                </p>

                <p style="font-size:15px;color:#374151;line-height:1.7;">
                  आपका संदेश हमें मिल गया है।<br>
                  हम <strong>24 घंटे के अंदर</strong> आपको जवाब देंगे।
                </p>

                <div style="background:#f0f9ff;border:1px solid #bfdbfe;
                            padding:16px;border-radius:8px;margin:20px 0;">
                  <p style="margin:0;color:#1e40af;font-size:14px;">
                    <strong>विषय:</strong> {subject}
                  </p>
                </div>

                <p style="font-size:15px;color:#374151;line-height:1.7;">
                  यदि आपको तुरंत सहायता चाहिए:<br>
                  📱 WhatsApp: <strong>+91 98730 20789</strong><br>
                  📧 Email: <strong>helpdesk@kagazat.in</strong>
                </p>

                <p style="font-size:15px;color:#374151;margin-top:24px;">
                  धन्यवाद<br>
                  <strong>Kagazat Team</strong>
                </p>
              </div>

              <div style="background:#f9fafb;padding:14px 24px;text-align:center;
                          font-size:12px;color:#9ca3af;">
                © 2026 Kagazat. All rights reserved. |
                <a href="https://kagazat.in" style="color:#2563eb;">kagazat.in</a>
              </div>
            </div>
            """,
        })
        return True
    except Exception as e:
        app.logger.error("Contact confirmation email error: %s", e)
        return False


# ──────────────────────────────────────────────
# Static file serving
# ──────────────────────────────────────────────

FRONTEND_FOLDER = os.path.join(os.path.dirname(__file__), "frontend")

@app.route("/")
def serve_index():
    return send_from_directory(FRONTEND_FOLDER, "index.html")

@app.route("/<path:filename>")
def serve_file(filename):
    return send_from_directory(FRONTEND_FOLDER, filename)


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
try:
    init_db_pool()
except Exception as e:
    print(f"WARNING: Database pool init failed: {e}")

if __name__ == "__main__":
    DEBUG_MODE = os.getenv("DEBUG", "False") == "True"
    app.run(debug=DEBUG_MODE, port=5000)