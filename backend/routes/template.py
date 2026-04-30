from flask import Blueprint, jsonify, request
from db import get_db_connection
from auth_middleware import login_required

template_bp = Blueprint("template", __name__)

@template_bp.route("/template", methods=["GET"])
@login_required
def get_template():
    state_id      = request.args.get("state_id")
    court_id      = request.args.get("court_id")
    department_id = request.args.get("department_id")
    type_id       = request.args.get("type_id")

    if not all([state_id, court_id, department_id, type_id]):
        return jsonify({
            "error": "state_id, court_id, department_id, type_id all required"
        }), 400

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, html
        FROM affidavit_templates
        WHERE state_id = %s
          AND court_id = %s
          AND department_id = %s
          AND type_id = %s
          AND is_active = TRUE
        LIMIT 1
    """, (state_id, court_id, department_id, type_id))

    row = cur.fetchone()

    cur.close()
    conn.close()

    if not row:
        return jsonify({"error": "No template found for this combination"}), 404

    return jsonify(row), 200   # ✅ cleaner