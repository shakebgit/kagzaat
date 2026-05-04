"""
extensions/limiter.py — Flask-Limiter Instance
Created here so it can be imported by routes WITHOUT circular imports.
app.py calls limiter.init_app(app) after creating the Flask app.
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
)
