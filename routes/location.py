"""
routes/location.py — States + Cities
"""

from flask import Blueprint, jsonify, request
from extensions.db import get_db_connection

location_bp = Blueprint("location", __name__)


@location_bp.route("/states", methods=["GET"])
def get_states():
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM states ORDER BY name")
        rows = cur.fetchall()
    return jsonify(rows), 200


@location_bp.route("/cities", methods=["GET"])
def get_cities():
    state_id = request.args.get("state_id")
    if not state_id:
        return jsonify({"status": "error", "message": "state_id required"}), 400

    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name FROM cities WHERE state_id = %s ORDER BY name",
            (state_id,),
        )
        rows = cur.fetchall()
    return jsonify(rows), 200
