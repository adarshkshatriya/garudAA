from database.db_manager import DBManager

class Monitor:
    @staticmethod
    def get_all(user_id=None):
        db = DBManager()
        try:
            # Adjusted query for better SQLite compatibility
            query = """
                SELECT m.*,
                       (SELECT status FROM checks WHERE monitor_id = m.id ORDER BY timestamp DESC LIMIT 1) AS last_status,
                       (SELECT response_time FROM checks WHERE monitor_id = m.id ORDER BY timestamp DESC LIMIT 1) AS last_response_time,
                       (SELECT timestamp FROM checks WHERE monitor_id = m.id ORDER BY timestamp DESC LIMIT 1) AS last_checked,
                       s.expiry_date, s.days_remaining, s.issuer
                FROM monitors m
                LEFT JOIN ssl_info s ON s.monitor_id = m.id
                WHERE m.enabled = 1
            """
            params = []
            if user_id is not None:
                query += " AND m.user_id = %s"
                params.append(user_id)
                
            query += " ORDER BY m.created_at DESC"
            rows = db.query(query, params)
            return rows
        except Exception as e:
            print(f"Error in Monitor.get_all: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            db.close()

    @staticmethod
    def get_by_id(monitor_id, user_id=None):
        db = DBManager()
        query = "SELECT * FROM monitors WHERE id = %s"
        params = [monitor_id]
        if user_id is not None:
            query += " AND user_id = %s"
            params.append(user_id)
        row = db.query_one(query, params)
        db.close()
        return row

    @staticmethod
    def create(user_id, url, name=None, threshold=3000, alert_email=None):
        db = DBManager()
        monitor_id = db.execute(
            "INSERT INTO monitors (user_id, url, name, threshold, alert_email) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (user_id, url.strip(), name or url.strip(), threshold, alert_email)
        )
        db.close()
        return monitor_id

    @staticmethod
    def delete(monitor_id, user_id=None):
        db = DBManager()
        query = "DELETE FROM monitors WHERE id = %s"
        params = [monitor_id]
        if user_id is not None:
            query += " AND user_id = %s"
            params.append(user_id)
        db.execute(query, params)
        db.close()

class Check:
    @staticmethod
    def insert(monitor_id, status, response_time=None, status_code=None, error_msg=None):
        db = DBManager()
        db.execute(
            "INSERT INTO checks (monitor_id, status, response_time, status_code, error_msg) VALUES (%s, %s, %s, %s, %s)",
            (monitor_id, status, response_time, status_code, error_msg)
        )
        db.close()

    @staticmethod
    def get_history(monitor_id, limit=100):
        db = DBManager()
        rows = db.query(
            "SELECT status, response_time, timestamp, status_code FROM checks WHERE monitor_id = %s ORDER BY timestamp DESC LIMIT %s",
            (monitor_id, limit)
        )
        db.close()
        return rows

    @staticmethod
    def get_uptime_percent(monitor_id, hours=24):
        db = DBManager()
        row = db.query_one("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'UP' THEN 1 ELSE 0 END) AS up_count
            FROM checks
            WHERE monitor_id = %s
              AND timestamp >= NOW() - INTERVAL '1 hour' * %s
        """, (monitor_id, hours))
        db.close()
        if row and row["total"] > 0:
            return round(row["up_count"] / row["total"] * 100, 2)
        return None

    @staticmethod
    def get_avg_response(monitor_id, hours=24):
        db = DBManager()
        row = db.query_one("""
            SELECT AVG(response_time) AS avg_rt
            FROM checks
            WHERE monitor_id = %s AND status = 'UP'
              AND timestamp >= NOW() - INTERVAL '1 hour' * %s
        """, (monitor_id, hours))
        db.close()
        return round(row["avg_rt"], 1) if row and row["avg_rt"] else None

    @staticmethod
    def get_global_metrics(user_id=None):
        db = DBManager()
        query = """
            SELECT
                COUNT(DISTINCT c.monitor_id) AS total_monitors,
                AVG(CASE WHEN c.status='UP' THEN 100.0 ELSE 0 END) AS uptime_pct,
                AVG(CASE WHEN c.status='UP' THEN c.response_time END) AS avg_rt
            FROM checks c
        """
        params = []
        if user_id is not None:
            query += " JOIN monitors m ON m.id = c.monitor_id WHERE c.timestamp >= NOW() - INTERVAL '24 hours' AND m.user_id = %s"
            params.append(user_id)
        else:
            query += " WHERE c.timestamp >= NOW() - INTERVAL '24 hours'"
            
        row = db.query_one(query, params)
        db.close()
        return row if row else {}

    @staticmethod
    def get_timeseries(monitor_id, hours=24):
        db = DBManager()
        rows = db.query("""
            SELECT
                TO_CHAR(timestamp, 'YYYY-MM-DD"T"HH24:00:00') AS bucket,
                AVG(CASE WHEN status='UP' THEN 100.0 ELSE 0 END) AS uptime,
                AVG(CASE WHEN status='UP' THEN response_time END) AS avg_rt
            FROM checks
            WHERE monitor_id = %s
              AND timestamp >= NOW() - INTERVAL '1 hour' * %s
            GROUP BY bucket
            ORDER BY bucket ASC
        """, (monitor_id, hours))
        db.close()
        return rows

    @staticmethod
    def get_global_timeseries(hours=24, user_id=None):
        db = DBManager()
        query = """
            SELECT
                TO_CHAR(c.timestamp, 'YYYY-MM-DD"T"HH24:00:00') AS bucket,
                AVG(CASE WHEN c.status='UP' THEN 100.0 ELSE 0 END) AS uptime,
                AVG(CASE WHEN c.status='UP' THEN c.response_time END) AS avg_rt
            FROM checks c
        """
        params = [hours]
        if user_id is not None:
            query += " JOIN monitors m ON m.id = c.monitor_id WHERE c.timestamp >= NOW() - INTERVAL '1 hour' * %s AND m.user_id = %s"
            params.append(user_id)
        else:
            query += " WHERE c.timestamp >= NOW() - INTERVAL '1 hour' * %s"
            
        query += " GROUP BY bucket ORDER BY bucket ASC"
        rows = db.query(query, params)
        db.close()
        return rows


class SSLInfo:
    @staticmethod
    def upsert(monitor_id, expiry_date, days_remaining, issuer):
        db = DBManager()
        if db.sqlite:
            # SQLite upsert
            db.execute("""
                INSERT INTO ssl_info (monitor_id, expiry_date, days_remaining, issuer, last_checked)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT(monitor_id) DO UPDATE SET
                    expiry_date    = excluded.expiry_date,
                    days_remaining = excluded.days_remaining,
                    issuer         = excluded.issuer,
                    last_checked   = excluded.last_checked
            """, (monitor_id, expiry_date, days_remaining, issuer))
        else:
            db.execute("""
                INSERT INTO ssl_info (monitor_id, expiry_date, days_remaining, issuer)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT(monitor_id) DO UPDATE SET
                    expiry_date    = EXCLUDED.expiry_date,
                    days_remaining = EXCLUDED.days_remaining,
                    issuer         = EXCLUDED.issuer,
                    last_checked   = NOW()
            """, (monitor_id, expiry_date, days_remaining, issuer))
        db.close()

    @staticmethod
    def get_all(user_id=None):
        db = DBManager()
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
        rows = db.query(query, params)
        db.close()
        return rows

class Alert:
    @staticmethod
    def insert(monitor_id, alert_type, message):
        db = DBManager()
        db.execute("INSERT INTO alerts (monitor_id, type, message) VALUES (%s, %s, %s)", (monitor_id, alert_type, message))
        db.close()

    @staticmethod
    def get_recent(limit=50, user_id=None):
        db = DBManager()
        query = "SELECT a.*, m.url, m.name FROM alerts a JOIN monitors m ON m.id = a.monitor_id"
        params = []
        if user_id is not None:
            query += " WHERE m.user_id = %s"
            params.append(user_id)
        query += " ORDER BY a.timestamp DESC LIMIT %s"
        params.append(limit)
        rows = db.query(query, params)
        db.close()
        return rows

    @staticmethod
    def get_last_alert_time(monitor_id, alert_type):
        db = DBManager()
        row = db.query_one("""
            SELECT timestamp FROM alerts
            WHERE monitor_id = %s AND type = %s
            ORDER BY timestamp DESC LIMIT 1
        """, (monitor_id, alert_type))
        db.close()
        return row["timestamp"] if row else None
