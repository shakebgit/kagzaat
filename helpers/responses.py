"""
helpers/responses.py — Standardised API Responses
Every route returns one of these. No more mixed formats.

Shape:
  success → { "status": "success", "data": {}, "message": "..." }
  error   → { "status": "error",   "data": {}, "message": "...", "errors": [] }
"""

from flask import jsonify


def ok(data=None, message="Success", code=200):
    return jsonify({
        "status":  "success",
        "data":    data or {},
        "message": message,
    }), code


def fail(message="Error", code=400, errors=None):
    body = {
        "status":  "error",
        "data":    {},
        "message": message,
    }
    if errors:
        body["errors"] = errors
    return jsonify(body), code
