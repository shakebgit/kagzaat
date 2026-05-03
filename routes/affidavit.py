"""
routes/affidavit.py — Affidavit CRUD
save, list, get, update
"""

import uuid
import json
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request

from extensions.db import get_db_connection
from middleware.auth import require_auth

affidavit_bp = Blueprint("affidavit", __name__)


def _make_title(form_data: dict, default: str = "हलफनामा") -> str:
    name = (
        form_data.get("name") or
        form_data.get("full_name") or
        ""
    ).strip()
    return f"{default} — {name}" if name else default


# ── Save new ──────────────────────────────────────────────────
@affidavit_bp.route("/affidavit/save", methods=["POST"])
@require_auth
def save_affidavit():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"status": "error", "message": "JSON body required"}), 400

    required = ["user_id", "template_id", "form_data", "generated_html"]
    missing  = [k for k in required if k not in body]
    if missing:
        return jsonify({"status": "error", "message": f"Missing fields: {missing}"}), 400

    # Use authenticated user_id — never trust body["user_id"] alone
    user_id = request.user_id or request.user_email
    if not user_id:
        return jsonify({"status": "error", "message": "User identity missing"}), 401

    fd           = body.get("form_data") or {}
    title        = _make_title(fd, body.get("type_name", "हलफनामा"))
    affidavit_id = str(uuid.uuid4())
    now          = datetime.now(timezone.utc)

    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO affidavits (
                id, user_id, template_id, form_data, generated_html, title,
                state_id, city_id, court_id, department_id, type_id,
                created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                affidavit_id,
                user_id,
                body["template_id"],
                json.dumps(body["form_data"]),
                body["generated_html"],
                title,
                body.get("state_id"),
                body.get("city_id"),
                body.get("court_id"),
                body.get("department_id"),
                body.get("type_id"),
                now,
                now,
            ),
        )

    return jsonify({"status": "success", "id": affidavit_id, "title": title}), 201


# ── List user's affidavits ────────────────────────────────────
@affidavit_bp.route("/affidavit/user/<user_id>", methods=["GET"])
@require_auth
def get_user_affidavits(user_id):
    # Ownership: URL user_id must match token user_id
    print(f"Request user_id: {request.user_id}")
    print(f"Request_URL user_id: {user_id}")
    if str(user_id) != str(request.user_id):
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, title, created_at, updated_at,
                   state_id, court_id, department_id, type_id
            FROM affidavits
            WHERE user_id = %s
            ORDER BY updated_at DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()

    return jsonify(rows), 200


# ── Get single affidavit ──────────────────────────────────────
@affidavit_bp.route("/affidavit/<affidavit_id>", methods=["GET"])
@require_auth
def get_affidavit(affidavit_id):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT a.*, t.html AS template_html, t.name AS template_name
            FROM affidavits a
            LEFT JOIN affidavit_templates t ON a.template_id = t.id
            WHERE a.id = %s
            """,
            (affidavit_id,),
        )
        row = cur.fetchone()

    if not row:
        return jsonify({"status": "error", "message": "Not found"}), 404

    if str(row["user_id"]) != str(request.user_id):
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    return jsonify(row), 200


# ── Update existing ───────────────────────────────────────────
@affidavit_bp.route("/affidavit/update/<affidavit_id>", methods=["PUT"])
@require_auth
def update_affidavit(affidavit_id):
    with get_db_connection() as conn:
        cur = conn.cursor()

        cur.execute("SELECT user_id FROM affidavits WHERE id = %s", (affidavit_id,))
        existing = cur.fetchone()

        if not existing:
            return jsonify({"status": "error", "message": "Not found"}), 404

        if str(existing["user_id"]) != str(request.user_id):
            return jsonify({"status": "error", "message": "Forbidden"}), 403

        body   = request.get_json(silent=True) or {}
        fields = []
        values = []

        if "form_data" in body:
            fields.append("form_data = %s")
            values.append(json.dumps(body["form_data"]))
            fields.append("title = %s")
            values.append(_make_title(body["form_data"]))

        if "generated_html" in body:
            fields.append("generated_html = %s")
            values.append(body["generated_html"])

        fields.append("updated_at = %s")
        values.append(datetime.now(timezone.utc))
        values.append(affidavit_id)

        cur.execute(
            f"UPDATE affidavits SET {', '.join(fields)} WHERE id = %s",
            tuple(values),
        )

    return jsonify({"status": "success", "id": affidavit_id, "updated": True}), 200
