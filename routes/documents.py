"""
routes/documents.py — Document Routes
generate_pdf   → returns PDF directly (no disk write — Railway safe)
download_file  → serves saved PDFs with ownership check
usertempletdetails → legacy name-change data save
"""

import os
import re
from datetime import datetime
from flask import Blueprint, request, Response, send_from_directory, current_app

import bleach
from weasyprint import HTML

from extensions.db import get_db_connection
from helpers.responses import ok, fail
from helpers.email import send_pdf_email
from middleware.auth import require_auth
from config.settings import DOWNLOAD_FOLDER

documents_bp = Blueprint("documents", __name__)

# WeasyPrint: block all external resources
def _blocked_url_fetcher(url):
    raise Exception("External resources blocked")

_ALLOWED_TAGS = [
    "p", "b", "i", "u", "strong", "em",
    "h1", "h2", "h3", "ul", "ol", "li",
    "br", "span", "div", "table", "tr", "td", "th",
]


@documents_bp.route("/generate_pdf", methods=["POST"])
@require_auth
def generate_pdf():
    try:
        data = request.json or {}
        html = data.get("html", "")

        # Sanitize
        safe_html = bleach.clean(
            html,
            tags=_ALLOWED_TAGS,
            attributes={"*": ["style"]},
            strip=True,
        )

        # Block any surviving URLs
        if re.search(r"(http://|https://|file://|ftp://|//)", safe_html.lower()):
            return fail("External resources not allowed in document HTML.")

        user_email = request.user_email
        user_id    = request.user_id
        timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename   = f"affidavit_{user_id}_{timestamp}.pdf"

        # Generate PDF — entirely in memory, no disk write
        pdf_bytes = HTML(
            string=safe_html,
            url_fetcher=_blocked_url_fetcher,
            base_url=None,
        ).write_pdf()

        # Send email with attachment (non-blocking — failures logged, not raised)
        try:
            send_pdf_email(user_email, pdf_bytes, filename)
        except Exception as email_err:
            current_app.logger.warning("PDF email failed (non-fatal): %s", email_err)

        # Return PDF directly to browser
        return Response(
            pdf_bytes,
            status=200,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )

    except Exception as e:
        current_app.logger.error("generate_pdf error: %s", e)
        return fail("PDF generation failed. Please try again.", 500)


@documents_bp.route("/downloads/<filename>", methods=["GET"])
@require_auth
def download_file(filename):
    """
    Serves a saved PDF. Ownership enforced: filename must contain user_id.
    """
    safe_filename = os.path.basename(filename)

    # Ownership check — filename pattern: affidavit_{user_id}_{timestamp}.pdf
    if not safe_filename.startswith(f"affidavit_{request.user_id}_"):
        return fail("Forbidden", 403)

    return send_from_directory(
        os.path.abspath(DOWNLOAD_FOLDER),
        safe_filename,
        as_attachment=True,
    )


@documents_bp.route("/usertempletdetails", methods=["POST"])
@require_auth
def usertempletdetails():
    """Legacy endpoint — saves name-change affidavit form data."""
    try:
        from helpers.sanitizers import sanitize_input

        data       = request.json or {}
        userid     = request.user_email

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO usertempletdetails
                    (currentname, newname, guardianname, age, dob, sex,
                     address, reason, mobile, adhar, userid)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    sanitize_input(data.get("currentname")),
                    sanitize_input(data.get("newname")),
                    sanitize_input(data.get("fathername")),
                    sanitize_input(data.get("age")),
                    sanitize_input(data.get("dob")),
                    sanitize_input(data.get("gender")),
                    sanitize_input(data.get("address")),
                    sanitize_input(data.get("reason")),
                    sanitize_input(data.get("mobile")),
                    sanitize_input(data.get("aadhaar")),
                    userid,
                ),
            )

        return ok(message="Template data saved"), 201

    except Exception as e:
        current_app.logger.error("usertempletdetails error: %s", e)
        return fail("Server error", 500)
