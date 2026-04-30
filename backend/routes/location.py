from flask import Blueprint, jsonify, request
from db import get_db_connection

location_bp = Blueprint("location", __name__)

# GET /states
@location_bp.route("/states", methods=["GET"])
def get_states():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, name FROM states ORDER BY name")
    rows = cur.fetchall()

    cur.close()
    conn.close()

    # convert to JSON
    #data = [{"id": r[0], "name": r[1]} for r in rows]
    data = rows

    return jsonify(data), 200


# GET /cities?state_id=1
@location_bp.route("/cities", methods=["GET"])
def get_cities():
    state_id = request.args.get("state_id")

    if not state_id:
        return jsonify({"error": "state_id required"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, name FROM cities WHERE state_id = %s ORDER BY name",
        (state_id,)
    )
    rows = cur.fetchall()

    cur.close()
    conn.close()

    #data = [{"id": r[0], "name": r[1]} for r in rows]
    data = rows

    return jsonify(data), 200