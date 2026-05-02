import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_connection():
    # Use DATABASE_URL from environment
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    conn = psycopg2.connect(db_url)
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            google_id TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            picture TEXT,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS monitors (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL,
            url         TEXT    NOT NULL,
            name        TEXT,
            interval    INTEGER DEFAULT 60,
            threshold   INTEGER DEFAULT 3000,
            alert_email TEXT,
            enabled     INTEGER DEFAULT 1,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS checks (
            id           SERIAL PRIMARY KEY,
            monitor_id   INTEGER NOT NULL,
            status       TEXT    NOT NULL,
            response_time REAL,
            status_code  INTEGER,
            error_msg    TEXT,
            timestamp    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (monitor_id) REFERENCES monitors(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ssl_info (
            id             SERIAL PRIMARY KEY,
            monitor_id     INTEGER NOT NULL UNIQUE,
            expiry_date    TEXT,
            days_remaining INTEGER,
            issuer         TEXT,
            last_checked   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (monitor_id) REFERENCES monitors(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id         SERIAL PRIMARY KEY,
            monitor_id INTEGER NOT NULL,
            type       TEXT    NOT NULL,
            message    TEXT    NOT NULL,
            sent       INTEGER DEFAULT 0,
            timestamp  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (monitor_id) REFERENCES monitors(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_checks_monitor_time
            ON checks(monitor_id, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_alerts_monitor
            ON alerts(monitor_id, timestamp DESC);
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("[DB] Initialized with PostgreSQL")
