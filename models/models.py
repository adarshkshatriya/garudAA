from database.schema import get_connection


class Monitor:
    @staticmethod
    def get_all(user_id=None):
        conn = get_connection()
        query = """
            SELECT m.*,
                   c.status        AS last_status,
                   c.response_time AS last_response_time,
                   c.timestamp     AS last_checked,
                   c.status_code   AS last_status_code,
                   c.error_msg     AS last_error,
                   s.expiry_date, s.days_remaining, s.issuer
            FROM monitors m
            LEFT JOIN checks c ON c.id = (
                SELECT id FROM checks WHERE monitor_id = m.id ORDER BY timestamp DESC LIMIT 1
            )
            LEFT JOIN ssl_info s ON s.monitor_id = m.id
            WHERE m.enabled = 1
        """
        params = []
        if user_id is not None:
            query += " AND m.user_id = ?"
            params.append(user_id)
            
        query += " ORDER BY m.created_at DESC"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_by_id(monitor_id, user_id=None):
        conn = get_connection()
        query = "SELECT * FROM monitors WHERE id = ?"
        params = [monitor_id]
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)
        row = conn.execute(query, params).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def create(user_id, url, name=None, threshold=3000, alert_email=None):
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO monitors (user_id, url, name, threshold, alert_email) VALUES (?, ?, ?, ?, ?)",
                (user_id, url.strip(), name or url.strip(), threshold, alert_email)
            )
            conn.commit()
            monitor_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        finally:
            conn.close()
        return monitor_id

    @staticmethod
    def delete(monitor_id, user_id=None):
        conn = get_connection()
        query = "DELETE FROM monitors WHERE id = ?"
        params = [monitor_id]
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)
        conn.execute(query, params)
        conn.commit()
        conn.close()

    @staticmethod
    def update_email(monitor_id, email, user_id=None):
        conn = get_connection()
        query = "UPDATE monitors SET alert_email = ? WHERE id = ?"
        params = [email, monitor_id]
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)
        conn.execute(query, params)
        conn.commit()
        conn.close()


class Check:
    @staticmethod
    def insert(monitor_id, status, response_time=None, status_code=None, error_msg=None):
        conn = get_connection()
        conn.execute(
            """INSERT INTO checks (monitor_id, status, response_time, status_code, error_msg)
               VALUES (?, ?, ?, ?, ?)""",
            (monitor_id, status, response_time, status_code, error_msg)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_history(monitor_id, limit=100):
        conn = get_connection()
        rows = conn.execute(
            """SELECT status, response_time, timestamp, status_code
               FROM checks WHERE monitor_id = ?
               ORDER BY timestamp DESC LIMIT ?""",
            (monitor_id, limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_uptime_percent(monitor_id, hours=24):
        conn = get_connection()
        row = conn.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'UP' THEN 1 ELSE 0 END) AS up_count
            FROM checks
            WHERE monitor_id = ?
              AND timestamp >= datetime('now', ? || ' hours')
        """, (monitor_id, f"-{hours}")).fetchone()
        conn.close()
        if row and row["total"] > 0:
            return round(row["up_count"] / row["total"] * 100, 2)
        return None

    @staticmethod
    def get_avg_response(monitor_id, hours=24):
        conn = get_connection()
        row = conn.execute("""
            SELECT AVG(response_time) AS avg_rt
            FROM checks
            WHERE monitor_id = ? AND status = 'UP'
              AND timestamp >= datetime('now', ? || ' hours')
        """, (monitor_id, f"-{hours}")).fetchone()
        conn.close()
        return round(row["avg_rt"], 1) if row and row["avg_rt"] else None

    @staticmethod
    def get_global_metrics(user_id=None):
        conn = get_connection()
        query = """
            SELECT
                COUNT(DISTINCT c.monitor_id)                              AS total_monitors,
                ROUND(AVG(CASE WHEN c.status='UP' THEN 100.0 ELSE 0 END),2) AS uptime_pct,
                ROUND(AVG(CASE WHEN c.status='UP' THEN c.response_time END),1) AS avg_rt
            FROM checks c
        """
        params = []
        if user_id is not None:
            query += " JOIN monitors m ON m.id = c.monitor_id WHERE c.timestamp >= datetime('now', '-24 hours') AND m.user_id = ?"
            params.append(user_id)
        else:
            query += " WHERE c.timestamp >= datetime('now', '-24 hours')"
            
        row = conn.execute(query, params).fetchone()
        conn.close()
        return dict(row) if row else {}

    @staticmethod
    def get_timeseries(monitor_id, hours=24, buckets=24):
        conn = get_connection()
        rows = conn.execute("""
            SELECT
                strftime('%Y-%m-%dT%H:00:00', timestamp) AS bucket,
                ROUND(AVG(CASE WHEN status='UP' THEN 100.0 ELSE 0 END),1) AS uptime,
                ROUND(AVG(CASE WHEN status='UP' THEN response_time END),1) AS avg_rt
            FROM checks
            WHERE monitor_id = ?
              AND timestamp >= datetime('now', ? || ' hours')
            GROUP BY bucket
            ORDER BY bucket ASC
        """, (monitor_id, f"-{hours}")).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_global_timeseries(hours=24, user_id=None):
        conn = get_connection()
        query = """
            SELECT
                strftime('%Y-%m-%dT%H:00:00', c.timestamp) AS bucket,
                ROUND(AVG(CASE WHEN c.status='UP' THEN 100.0 ELSE 0 END),1) AS uptime,
                ROUND(AVG(CASE WHEN c.status='UP' THEN c.response_time END),1) AS avg_rt
            FROM checks c
        """
        params = [f"-{hours}"]
        if user_id is not None:
            query += " JOIN monitors m ON m.id = c.monitor_id WHERE c.timestamp >= datetime('now', ? || ' hours') AND m.user_id = ?"
            params.append(user_id)
        else:
            query += " WHERE c.timestamp >= datetime('now', ? || ' hours')"
            
        query += " GROUP BY bucket ORDER BY bucket ASC"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]


class SSLInfo:
    @staticmethod
    def upsert(monitor_id, expiry_date, days_remaining, issuer):
        conn = get_connection()
        conn.execute("""
            INSERT INTO ssl_info (monitor_id, expiry_date, days_remaining, issuer)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(monitor_id) DO UPDATE SET
                expiry_date    = excluded.expiry_date,
                days_remaining = excluded.days_remaining,
                issuer         = excluded.issuer,
                last_checked   = datetime('now')
        """, (monitor_id, expiry_date, days_remaining, issuer))
        conn.commit()
        conn.close()

    @staticmethod
    def get_all(user_id=None):
        conn = get_connection()
        query = """
            SELECT s.*, m.url, m.name
            FROM ssl_info s
            JOIN monitors m ON m.id = s.monitor_id
            WHERE m.enabled = 1
        """
        params = []
        if user_id is not None:
            query += " AND m.user_id = ?"
            params.append(user_id)
            
        query += " ORDER BY s.days_remaining ASC"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]


class Alert:
    @staticmethod
    def insert(monitor_id, alert_type, message):
        conn = get_connection()
        conn.execute(
            "INSERT INTO alerts (monitor_id, type, message) VALUES (?, ?, ?)",
            (monitor_id, alert_type, message)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_recent(limit=50, user_id=None):
        conn = get_connection()
        query = """
            SELECT a.*, m.url, m.name
            FROM alerts a
            JOIN monitors m ON m.id = a.monitor_id
        """
        params = []
        if user_id is not None:
            query += " WHERE m.user_id = ?"
            params.append(user_id)
            
        query += " ORDER BY a.timestamp DESC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_last_alert_time(monitor_id, alert_type):
        conn = get_connection()
        row = conn.execute("""
            SELECT timestamp FROM alerts
            WHERE monitor_id = ? AND type = ?
            ORDER BY timestamp DESC LIMIT 1
        """, (monitor_id, alert_type)).fetchone()
        conn.close()
        return row["timestamp"] if row else None
