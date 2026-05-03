"""
extensions/db.py — Database Connection Pool
Single pool instance shared across the entire app.
Import get_db_connection anywhere you need a DB connection.
"""

import logging
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

_pool = None


def init_pool(database_url: str, minconn: int = 1, maxconn: int = 20):
    """Called once at app startup from app.py."""
    global _pool
    _pool = pool.ThreadedConnectionPool(
        minconn=minconn,
        maxconn=maxconn,
        dsn=database_url,
        cursor_factory=RealDictCursor,   # rows as dicts everywhere
    )
    logger.info("DB pool initialised (min=%s, max=%s)", minconn, maxconn)


@contextmanager
def get_db_connection():
    """
    Usage:
        with get_db_connection() as conn:
            cur = conn.cursor()
            ...
    Commits on success, rolls back on exception, always returns conn to pool.
    """
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_pool() first")

    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


def is_pool_ready() -> bool:
    return _pool is not None
