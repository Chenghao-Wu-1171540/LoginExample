"""
loginapp/db.py - PostgreSQL database connection utilities

This module provides:
- init_db(app): Initialize connection pool at app startup
- get_db(): Get a connection from the pool (per-request)
- close_db(exception): Close connection at end of request
"""

import psycopg2
from psycopg2.pool import SimpleConnectionPool
from flask import current_app, g

# 從 connect.py 匯入資料庫連線參數
import connect

# Global connection pool
pool = None


def init_db(app):
    """
    Initialize PostgreSQL connection pool when app starts.
    Pool is created once and reused for all requests.
    """
    global pool

    # 使用 connect.py 裡定義的參數
    db_params = {
        'dbname': connect.dbname,
        'user': connect.dbuser,
        'password': connect.dbpass,
        'host': connect.dbhost,
        'port': connect.dbport
    }

    pool = SimpleConnectionPool(
        minconn=1,
        maxconn=20,
        **db_params
    )

    # Optional: test connection on startup
    try:
        conn = pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT version();")
        print("PostgreSQL connected successfully:", cur.fetchone()[0])
        cur.close()
        pool.putconn(conn)
    except Exception as e:
        print("Failed to connect to PostgreSQL:", e)

    # Register teardown function
    app.teardown_appcontext(close_db)


def get_db():
    """
    Get a database connection for the current request.
    Uses Flask's g to cache the connection per request.
    """
    if 'db' not in g:
        g.db = pool.getconn()
    return g.db


def close_db(exception=None):
    """
    Close the database connection at the end of the request.
    Returns connection to the pool.
    """
    db = g.pop('db', None)
    if db is not None:
        pool.putconn(db)