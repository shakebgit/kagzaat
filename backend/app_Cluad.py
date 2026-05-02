"""
app.py — Kagazat Flask Entry Point
Registers all blueprints. Serves frontend static files.
Your existing auth routes (login, logout, check-auth, register)
are imported from their existing module — do not duplicate them here.
"""
from flask import Flask, send_from_directory
from flask_cors import CORS
from backend.config import Config

# ── Existing auth blueprint (your file — adjust import path if needed) ──
# from routes.auth import auth_bp

# ── New blueprints ────────────────────────────────────────────
from backend.routes.location import location_bp
from routes.lookup   import lookup_bp
from routes.template import template_bp
from routes.affidavit import affidavit_bp

app = Flask(__name__, static_folder="../frontend", static_url_path="")

app.config.from_object(Config)

# ── CORS — allow your frontend origin with cookies ────────────
CORS(app,
     origins=[Config.FRONTEND_ORIGIN],
     supports_credentials=True,
     allow_headers=["Content-Type"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# ── Register blueprints ───────────────────────────────────────
# app.register_blueprint(auth_bp)          # your existing auth
app.register_blueprint(location_bp)
app.register_blueprint(lookup_bp)
app.register_blueprint(template_bp)
app.register_blueprint(affidavit_bp)

# ── Serve frontend HTML files directly ───────────────────────
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def catch_all(path):
    # Serve any .html / .js / .css file from frontend folder
    try:
        return send_from_directory(app.static_folder, path)
    except Exception:
        return send_from_directory(app.static_folder, "index.html")

# ── Run ───────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=Config.DEBUG, port=5000)
