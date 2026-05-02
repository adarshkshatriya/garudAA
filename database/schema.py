import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "synthmon.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            google_id TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            picture TEXT,
            role TEXT DEFAULT 'user',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS monitors (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            url         TEXT    NOT NULL,
            name        TEXT,
            interval    INTEGER DEFAULT 60,
            threshold   INTEGER DEFAULT 3000,
            alert_email TEXT,
            enabled     INTEGER DEFAULT 1,
            created_at  TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS checks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            monitor_id   INTEGER NOT NULL,
            status       TEXT    NOT NULL,
            response_time REAL,
            status_code  INTEGER,
            error_msg    TEXT,
            timestamp    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (monitor_id) REFERENCES monitors(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ssl_info (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            monitor_id     INTEGER NOT NULL UNIQUE,
            expiry_date    TEXT,
            days_remaining INTEGER,
            issuer         TEXT,
            last_checked   TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (monitor_id) REFERENCES monitors(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            monitor_id INTEGER NOT NULL,
            type       TEXT    NOT NULL,
            message    TEXT    NOT NULL,
            sent       INTEGER DEFAULT 0,
            timestamp  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (monitor_id) REFERENCES monitors(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_checks_monitor_time
            ON checks(monitor_id, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_alerts_monitor
            ON alerts(monitor_id, timestamp DESC);
    """)

    conn.commit()
    conn.close()
    print(f"[DB] Initialized at {DB_PATH}")
