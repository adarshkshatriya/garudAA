import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "synthmon.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    # Important: turn OFF foreign keys so dropping monitors doesn't cascade-delete checks
    conn.execute("PRAGMA foreign_keys=OFF")
    
    c = conn.cursor()
    
    # 1. Ensure at least one user exists for existing monitors
    c.execute("SELECT id FROM users LIMIT 1")
    user = c.fetchone()
    if not user:
        c.execute("""
            INSERT INTO users (google_id, email, name) 
            VALUES ('dummy_migration_id', 'admin@example.com', 'Admin User')
        """)
        conn.commit()
        user_id = c.lastrowid
    else:
        user_id = user[0]
        
    print(f"Using user_id {user_id} for existing monitors.")

    # 2. Create the new table
    c.executescript("""
        CREATE TABLE IF NOT EXISTS monitors_new (
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
    """)
    
    # 3. Copy data from old table to new table
    c.execute(f"""
        INSERT INTO monitors_new (id, user_id, url, name, interval, threshold, alert_email, enabled, created_at)
        SELECT id, {user_id}, url, name, interval, threshold, alert_email, enabled, created_at FROM monitors;
    """)
    
    # 4. Drop old table
    c.execute("DROP TABLE monitors;")
    
    # 5. Rename new table
    c.execute("ALTER TABLE monitors_new RENAME TO monitors;")
    
    conn.commit()
    conn.close()
    print("Database migration completed successfully!")

if __name__ == "__main__":
    migrate()
