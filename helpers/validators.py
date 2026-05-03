"""
helpers/validators.py — Input Validation
Pure functions, no Flask dependencies, easily unit-testable.
"""

import re


def validate_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_password(password: str) -> tuple[bool, str]:
    """Returns (is_valid, message)."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain an uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain a lowercase letter"
    if not re.search(r"[0-9]", password):
        return False, "Password must contain a number"
    return True, "Valid"


def validate_mobile(mobile: str) -> bool:
    """Indian mobile: 10 digits, starts with 6-9."""
    return bool(re.match(r"^[6-9]\d{9}$", mobile))
