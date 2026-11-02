from contextlib import contextmanager

import mysql.connector
from mysql.connector import pooling

from app.config import get_settings

_pool = None


def get_pool():
    global _pool
    if _pool is None:
        s = get_settings()
        _pool = pooling.MySQLConnectionPool(
            pool_name="borrownear_pool", pool_size=max(1, min(s.db_pool_size, 32)),
            host=s.database_host, port=s.database_port, database=s.database_name,
            user=s.database_user, password=s.database_password,
            autocommit=False, connection_timeout=5,
        )
    return _pool


def reset_pool_for_tests():
    global _pool
    _pool = None


@contextmanager
def connection():
    conn = get_pool().get_connection()
    try:
        yield conn
    except BaseException:
        # Pooled connections must not return an open/partial transaction to
        # the next request. Preserve the original exception if rollback fails.
        try:
            if conn.in_transaction:
                conn.rollback()
        except mysql.connector.Error:
            pass
        raise
    finally:
        conn.close()


@contextmanager
def cursor(dictionary=True):
    with connection() as conn:
        cur = conn.cursor(dictionary=dictionary)
        try:
            yield conn, cur
        finally:
            cur.close()
