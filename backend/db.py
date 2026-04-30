"""
db.py — PostgreSQL connection helper
Use get_db_connection() everywhere — single source of truth
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    return psycopg2.connect(
        os.environ.get("DATABASE_URL"),
        cursor_factory=RealDictCursor  
    )