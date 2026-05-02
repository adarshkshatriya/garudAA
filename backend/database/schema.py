import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor

def get_connection():
    db_url = os.environ.get("DATABASE_URL", "sqlite:///synthmon.db")
    
    if db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
        # PostgreSQL (Render / Production)
        conn = psycopg2.connect(db_url)
        return conn
    else:
        # SQLite (Local Testing)
        # Convert sqlite:///path to path
        path = db_url.replace("sqlite:///", "")
        conn = sqlite3.connect(path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_connection()
    is_sqlite = isinstance(conn, sqlite3.Connection)
    cur = conn.cursor()

    # Shared schema logic (adapted for both)
    # Using types that both understand or mapping them
    serial_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "SERIAL PRIMARY KEY"
    timestamp_type = "TEXT DEFAULT (datetime('now'))" if is_sqlite else "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"

    schema = f"""
        CREATE TABLE IF NOT EXISTS users (
            id {serial_type},
            google_id TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            picture TEXT,
            role TEXT DEFAULT 'user',
            created_at {timestamp_type}
        );

        CREATE TABLE IF NOT EXISTS monitors (
            id          {serial_type},
            user_id     INTEGER NOT NULL,
            url         TEXT    NOT NULL,
            name        TEXT,
            interval    INTEGER DEFAULT 60,
            threshold   INTEGER DEFAULT 3000,
            alert_email TEXT,
            enabled     INTEGER DEFAULT 1,
            created_at  {timestamp_type},
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS checks (
            id           {serial_type},
            monitor_id   INTEGER NOT NULL,
            status       TEXT    NOT NULL,
            response_time REAL,
            status_code  INTEGER,
            error_msg    TEXT,
            timestamp    {timestamp_type},
            FOREIGN KEY (monitor_id) REFERENCES monitors(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ssl_info (
            id             {serial_type},
            monitor_id     INTEGER NOT NULL UNIQUE,
            expiry_date    TEXT,
            days_remaining INTEGER,
            issuer         TEXT,
            last_checked   {timestamp_type},
            FOREIGN KEY (monitor_id) REFERENCES monitors(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id         {serial_type},
            monitor_id INTEGER NOT NULL,
            type       TEXT    NOT NULL,
            message    TEXT    NOT NULL,
            sent       INTEGER DEFAULT 0,
            timestamp  {timestamp_type},
            FOREIGN KEY (monitor_id) REFERENCES monitors(id) ON DELETE CASCADE
        );
    """
    
    if is_sqlite:
        cur.executescript(schema)
    else:
        cur.execute(schema)

    # Indices
    cur.execute("CREATE INDEX IF NOT EXISTS idx_checks_monitor_time ON checks(monitor_id, timestamp DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_alerts_monitor ON alerts(monitor_id, timestamp DESC)")

    conn.commit()
    cur.close()
    conn.close()
    print(f"[DB] Initialized with {'SQLite' if is_sqlite else 'PostgreSQL'}")
