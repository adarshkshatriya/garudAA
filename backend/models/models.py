from database.schema import get_connection
from psycopg2.extras import RealDictCursor

class Monitor:
    @staticmethod
    def get_all(user_id=None):
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT m.*,
                   c.status        AS last_status,
                   c.response_time AS last_response_time,
                   c.timestamp     AS last_checked,
                   c.status_code   AS last_status_code,
                   c.error_msg     AS last_error,
                   s.expiry_date, s.days_remaining, s.issuer
            FROM monitors m
            LEFT JOIN (
                SELECT DISTINCT ON (monitor_id) *
                FROM checks
                ORDER BY monitor_id, timestamp DESC
            ) c ON c.monitor_id = m.id
            LEFT JOIN ssl_info s ON s.monitor_id = m.id
            WHERE m.enabled = 1
        """
        params = []
        if user_id is not None:
            query += " AND m.user_id = %s"
            params.append(user_id)
            
        query += " ORDER BY m.created_at DESC"
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_by_id(monitor_id, user_id=None):
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = "SELECT * FROM monitors WHERE id = %s"
        params = [monitor_id]
        if user_id is not None:
            query += " AND user_id = %s"
            params.append(user_id)
        cur.execute(query, params)
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def create(user_id, url, name=None, threshold=3000, alert_email=None):
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO monitors (user_id, url, name, threshold, alert_email) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (user_id, url.strip(), name or url.strip(), threshold, alert_email)
            )
            monitor_id = cur.fetchone()[0]
            conn.commit()
        finally:
            cur.close()
            conn.close()
        return monitor_id

    @staticmethod
    def delete(monitor_id, user_id=None):
        conn = get_connection()
        cur = conn.cursor()
        query = "DELETE FROM monitors WHERE id = %s"
        params = [monitor_id]
        if user_id is not None:
            query += " AND user_id = %s"
            params.append(user_id)
        cur.execute(query, params)
        conn.commit()
        cur.close()
        conn.close()


class Check:
    @staticmethod
    def insert(monitor_id, status, response_time=None, status_code=None, error_msg=None):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO checks (monitor_id, status, response_time, status_code, error_msg)
               VALUES (%s, %s, %s, %s, %s)""",
            (monitor_id, status, response_time, status_code, error_msg)
        )
        conn.commit()
        cur.close()
        conn.close()

    @staticmethod
    def get_history(monitor_id, limit=100):
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """SELECT status, response_time, timestamp, status_code
               FROM checks WHERE monitor_id = %s
               ORDER BY timestamp DESC LIMIT %s""",
            (monitor_id, limit)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_uptime_percent(monitor_id, hours=24):
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'UP' THEN 1 ELSE 0 END) AS up_count
            FROM checks
            WHERE monitor_id = %s
              AND timestamp >= NOW() - INTERVAL '1 hour' * %s
        """, (monitor_id, hours))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row["total"] > 0:
            return round(row["up_count"] / row["total"] * 100, 2)
        return None

    @staticmethod
    def get_avg_response(monitor_id, hours=24):
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT AVG(response_time) AS avg_rt
            FROM checks
            WHERE monitor_id = %s AND status = 'UP'
              AND timestamp >= NOW() - INTERVAL '1 hour' * %s
        """, (monitor_id, hours))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return round(row["avg_rt"], 1) if row and row["avg_rt"] else None

    @staticmethod
    def get_global_metrics(user_id=None):
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT
                COUNT(DISTINCT c.monitor_id)                              AS total_monitors,
                ROUND(AVG(CASE WHEN c.status='UP' THEN 100.0 ELSE 0 END)::numeric, 2) AS uptime_pct,
                ROUND(AVG(CASE WHEN c.status='UP' THEN c.response_time END)::numeric, 1) AS avg_rt
            FROM checks c
        """
        params = []
        if user_id is not None:
            query += " JOIN monitors m ON m.id = c.monitor_id WHERE c.timestamp >= NOW() - INTERVAL '24 hours' AND m.user_id = %s"
            params.append(user_id)
        else:
            query += " WHERE c.timestamp >= NOW() - INTERVAL '24 hours'"
            
        cur.execute(query, params)
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else {}

    @staticmethod
    def get_timeseries(monitor_id, hours=24):
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT
                TO_CHAR(timestamp, 'YYYY-MM-DD"T"HH24:00:00') AS bucket,
                ROUND(AVG(CASE WHEN status='UP' THEN 100.0 ELSE 0 END)::numeric, 1) AS uptime,
                ROUND(AVG(CASE WHEN status='UP' THEN response_time END)::numeric, 1) AS avg_rt
            FROM checks
            WHERE monitor_id = %s
              AND timestamp >= NOW() - INTERVAL '1 hour' * %s
            GROUP BY bucket
            ORDER BY bucket ASC
        """, (monitor_id, hours))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_global_timeseries(hours=24, user_id=None):
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT
                TO_CHAR(c.timestamp, 'YYYY-MM-DD"T"HH24:00:00') AS bucket,
                ROUND(AVG(CASE WHEN c.status='UP' THEN 100.0 ELSE 0 END)::numeric, 1) AS uptime,
                ROUND(AVG(CASE WHEN c.status='UP' THEN c.response_time END)::numeric, 1) AS avg_rt
            FROM checks c
        """
        params = [hours]
        if user_id is not None:
            query += " JOIN monitors m ON m.id = c.monitor_id WHERE c.timestamp >= NOW() - INTERVAL '1 hour' * %s AND m.user_id = %s"
            params.append(user_id)
        else:
            query += " WHERE c.timestamp >= NOW() - INTERVAL '1 hour' * %s"
            
        query += " GROUP BY bucket ORDER BY bucket ASC"
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]


class SSLInfo:
    @staticmethod
    def upsert(monitor_id, expiry_date, days_remaining, issuer):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ssl_info (monitor_id, expiry_date, days_remaining, issuer)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT(monitor_id) DO UPDATE SET
                expiry_date    = EXCLUDED.expiry_date,
                days_remaining = EXCLUDED.days_remaining,
                issuer         = EXCLUDED.issuer,
                last_checked   = NOW()
        """, (monitor_id, expiry_date, days_remaining, issuer))
        conn.commit()
        cur.close()
        conn.close()

    @staticmethod
    def get_all(user_id=None):
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT s.*, m.url, m.name
            FROM ssl_info s
            JOIN monitors m ON m.id = s.monitor_id
            WHERE m.enabled = 1
        """
        params = []
        if user_id is not None:
            query += " AND m.user_id = %s"
            params.append(user_id)
            
        query += " ORDER BY s.days_remaining ASC"
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]


class Alert:
    @staticmethod
    def insert(monitor_id, alert_type, message):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO alerts (monitor_id, type, message) VALUES (%s, %s, %s)",
            (monitor_id, alert_type, message)
        )
        conn.commit()
        cur.close()
        conn.close()

    @staticmethod
    def get_recent(limit=50, user_id=None):
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT a.*, m.url, m.name
            FROM alerts a
            JOIN monitors m ON m.id = a.monitor_id
        """
        params = []
        if user_id is not None:
            query += " WHERE m.user_id = %s"
            params.append(user_id)
            
        query += " ORDER BY a.timestamp DESC LIMIT %s"
        params.append(limit)
        
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_last_alert_time(monitor_id, alert_type):
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT timestamp FROM alerts
            WHERE monitor_id = %s AND type = %s
            ORDER BY timestamp DESC LIMIT 1
        """, (monitor_id, alert_type))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row["timestamp"] if row else None
