"""
routes/lookup.py — Courts, Departments, Affidavit Types
"""

from flask import Blueprint, jsonify, request
from extensions.db import get_db_connection

lookup_bp = Blueprint("lookup", __name__)


@lookup_bp.route("/courts", methods=["GET"])
def get_courts():
    state_id = request.args.get("state_id")
    with get_db_connection() as conn:
        cur = conn.cursor()
        if state_id:
            cur.execute(
                "SELECT id, name FROM courts WHERE state_id = %s ORDER BY name",
                (state_id,),
            )
        else:
            cur.execute("SELECT id, name FROM courts ORDER BY name")
        rows = cur.fetchall()
    return jsonify(rows), 200


@lookup_bp.route("/departments", methods=["GET"])
def get_departments():
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM departments ORDER BY name")
        rows = cur.fetchall()
    return jsonify(rows), 200


@lookup_bp.route("/affidavit-types", methods=["GET"])
def get_affidavit_types():
    dept_id = request.args.get("department_id")
    with get_db_connection() as conn:
        cur = conn.cursor()
        if dept_id:
            cur.execute(
                "SELECT id, name FROM affidavit_types WHERE department_id = %s ORDER BY name",
                (dept_id,),
            )
        else:
            cur.execute("SELECT id, name FROM affidavit_types ORDER BY name")
        rows = cur.fetchall()
    return jsonify(rows), 200
