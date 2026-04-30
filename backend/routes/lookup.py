"""
routes/lookup.py (PostgreSQL version)
"""

from flask import Blueprint, jsonify, request
from db import get_db_connection

lookup_bp = Blueprint("lookup", __name__)


# ── GET /courts?state_id= ─────────────────────────────────────
@lookup_bp.route("/courts", methods=["GET"])
def get_courts():
    state_id = request.args.get("state_id")

    conn = get_db_connection()
    cur = conn.cursor()

    if state_id:
        cur.execute("""
            SELECT id, name
            FROM courts
            WHERE state_id = %s
            ORDER BY name
        """, (state_id,))
    else:
        cur.execute("""
            SELECT id, name
            FROM courts
            ORDER BY name
        """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    data = [dict(row) for row in rows]
    return jsonify(data), 200


# ── GET /departments ──────────────────────────────────────────
@lookup_bp.route("/departments", methods=["GET"])
def get_departments():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name
        FROM departments
        ORDER BY name
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    data = [dict(row) for row in rows]
    return jsonify(data), 200


# ── GET /affidavit-types?department_id= ───────────────────────
@lookup_bp.route("/affidavit-types", methods=["GET"])
def get_affidavit_types():
    dept_id = request.args.get("department_id")

    conn = get_db_connection()
    cur = conn.cursor()

    if dept_id:
        cur.execute("""
            SELECT id, name
            FROM affidavit_types
            WHERE department_id = %s
            ORDER BY name
        """, (dept_id,))
    else:
        cur.execute("""
            SELECT id, name
            FROM affidavit_types
            ORDER BY name
        """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    data = [dict(row) for row in rows]
    return jsonify(data), 200