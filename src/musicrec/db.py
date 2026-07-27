import psycopg
from pgvector.psycopg import register_vector

from musicrec.config import DATABASE_URL


def get_connection() -> psycopg.Connection:
    """Open a new connection with the pgvector type adapter registered.

    Short-lived script usage (ingestion, batch jobs) — callers are expected
    to use this as a context manager, not hold it open long-term.
    """
    conn = psycopg.connect(DATABASE_URL)
    register_vector(conn)
    return conn
