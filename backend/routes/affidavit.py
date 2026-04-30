"""
routes/affidavit.py (PostgreSQL version)
"""

from unittest import result
from unittest import result
import uuid
import json
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, g
from db import get_db_connection
from auth_middleware import login_required

affidavit_bp = Blueprint("affidavit", __name__)


# ── Save new ──────────────────────────────────────────────────
@affidavit_bp.route("/affidavit/save", methods=["POST"])
@login_required
def save_affidavit():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "JSON body required"}), 400

    required = ["user_id", "template_id", "form_data", "generated_html"]
    missing = [k for k in required if k not in body]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400
    

    effective = g.user_id or g.user_email
    if not effective:
        return jsonify({"error": "user_id missing — log out and log in again"}), 401

    fd = body.get("form_data") or {}
    print(fd)
    title = _make_title(fd, body.get("type_name", "हलफनामा"))

    conn = get_db_connection()
    cur = conn.cursor()

    affidavit_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    cur.execute("""
        INSERT INTO affidavits (
            id, user_id, template_id, form_data, generated_html, title,
            state_id, city_id, court_id, department_id, type_id,
            created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        affidavit_id,
        body["user_id"],
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
        now
    ))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"id": affidavit_id, "title": title}), 201


# ── List user's affidavits ────────────────────────────────────
@affidavit_bp.route("/affidavit/user/<user_id>", methods=["GET"])
@login_required
def get_user_affidavits(user_id):
    if str(user_id) != str(g.user_id):
        return jsonify({"error": "Forbidden"}), 403

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, created_at, updated_at,
               state_id, court_id, department_id, type_id
        FROM affidavits
        WHERE user_id = %s
        ORDER BY updated_at DESC
    """, (user_id,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    data = [dict(row) for row in rows]
    return jsonify(data), 200


# ── Get single affidavit ──────────────────────────────────────
@affidavit_bp.route("/affidavit/<affidavit_id>", methods=["GET"])
@login_required
def get_affidavit(affidavit_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT a.*, t.html AS template_html, t.name AS template_name
        FROM affidavits a
        LEFT JOIN affidavit_templates t
        ON a.template_id = t.id
        WHERE a.id = %s
    """, (affidavit_id,))

    row = cur.fetchone()

    cur.close()
    conn.close()

    if not row:
        return jsonify({"error": "Not found"}), 404

    if str(row["user_id"]) != str(g.user_id):
        return jsonify({"error": "Forbidden"}), 403

    # convert JSON string → dict
    #if row.get("form_data"):
        #row["form_data"] = json.loads(row["form_data"])
 
    return jsonify(row), 200


# ── Update existing ───────────────────────────────────────────
@affidavit_bp.route("/affidavit/update/<affidavit_id>", methods=["PUT"])
@login_required
def update_affidavit(affidavit_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Check ownership
    cur.execute("SELECT user_id FROM affidavits WHERE id = %s", (affidavit_id,))
    existing = cur.fetchone()

    if not existing:
        cur.close()
        conn.close()
        return jsonify({"error": "Not found"}), 404

    if str(existing["user_id"]) != str(g.user_id):
        cur.close()
        conn.close()
        return jsonify({"error": "Forbidden"}), 403

    body = request.get_json(silent=True) or {}

    fields = []
    values = []

    if "form_data" in body:
        fields.append("form_data = %s")
        values.append(json.dumps(body["form_data"]))

        fields.append("title = %s")
        values.append(_make_title(body["form_data"], "हलफनामा"))

    if "generated_html" in body:
        fields.append("generated_html = %s")
        values.append(body["generated_html"])

    fields.append("updated_at = %s")
    values.append(datetime.now(timezone.utc))

    values.append(affidavit_id)

    query = f"""
        UPDATE affidavits
        SET {', '.join(fields)}
        WHERE id = %s
    """

    cur.execute(query, tuple(values))
    conn.commit()

    cur.close()
    conn.close()

    return jsonify({"id": affidavit_id, "updated": True}), 200


# ── Helper ────────────────────────────────────────────────────
def _make_title(form_data: dict, default: str) -> str:
    name = (
        form_data.get("name") or
        form_data.get("full_name") or
        ""
    ).strip()

    if name:
        return f"{default} — {name}"

    return default