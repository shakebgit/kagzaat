"""
routes/contact.py — Public Contact Form
No auth required. Rate limited per IP.
"""

import json
from datetime import datetime
from flask import Blueprint, request, current_app

from extensions.db import get_db_connection
from extensions.limiter import limiter
from helpers.validators import validate_email, validate_mobile
from helpers.sanitizers import sanitize_input
from helpers.responses import ok, fail
from helpers.email import send_contact_notification, send_contact_confirmation

contact_bp = Blueprint("contact", __name__)


@contact_bp.route("/contact", methods=["POST"])
@limiter.limit("3 per 10 minutes")
def contact():
    try:
        data    = request.json or {}
        name    = sanitize_input(data.get("name", ""))
        email   = sanitize_input(data.get("email", ""))
        phone   = sanitize_input(data.get("phone", ""))
        subject = sanitize_input(data.get("subject", ""))
        message = sanitize_input(data.get("message", ""))

        if not name:
            return fail("Name is required.")
        if not validate_email(email):
            return fail("Invalid email address.")
        if not subject:
            return fail("Subject is required.")
        if not message or len(message) < 10:
            return fail("Message must be at least 10 characters.")
        if phone and not validate_mobile(phone):
            return fail("Invalid mobile number.")

        sender_ip = request.remote_addr
        timestamp = datetime.now().strftime("%d %b %Y, %I:%M %p")

        send_contact_notification(name, email, phone, subject, message, sender_ip, timestamp)
        send_contact_confirmation(name, email, subject)

        # Audit log — non-fatal if DB is unavailable
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO audit_log (user_email, action, ip_address, user_agent, meta)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        email, "CONTACT_FORM", sender_ip,
                        request.headers.get("User-Agent", ""),
                        json.dumps({"name": name, "subject": subject}),
                    ),
                )
        except Exception as db_err:
            current_app.logger.warning("Contact audit log failed: %s", db_err)

        return ok(message="Your message has been sent. We will reply within 24 hours.")

    except Exception as e:
        current_app.logger.error("Contact form error: %s", e)
        return fail("Server error. Please try again.", 500)
