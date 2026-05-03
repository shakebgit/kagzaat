"""
helpers/sanitizers.py — Input Sanitization
"""

import re


def sanitize_input(text) -> str:
    """Strip HTML tags and whitespace from any input."""
    if text is None:
        return ""
    return re.sub(r"<[^>]*>", "", str(text)).strip()
