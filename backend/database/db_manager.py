import sqlite3
import psycopg2
import re
from database.schema import get_connection

def is_sqlite(conn):
    return isinstance(conn, sqlite3.Connection)

def adapt_query(query, conn):
    if is_sqlite(conn):
        query = query.replace("%s", "?")
        query = query.replace("NOW()", "datetime('now')")
        query = query.replace("CURRENT_TIMESTAMP", "datetime('now')")
        query = query.replace("::numeric", "")
        query = query.replace("::text", "")
        query = re.sub(r"TO_CHAR\((.*?), 'YYYY-MM-DD\"T\"HH24:00:00'\)", r"strftime('%Y-%m-%dT%H:00:00', \1)", query)
        if " - INTERVAL '1 hour' * ?" in query:
            query = query.replace("datetime('now') - INTERVAL '1 hour' * ?", "datetime('now', '-' || ? || ' hours')")
        if " - INTERVAL '24 hours'" in query:
            query = query.replace("datetime('now') - INTERVAL '24 hours'", "datetime('now', '-24 hours')")
        if "RETURNING id" in query:
            query = query.replace("RETURNING id", "")
    return query

class DBManager:
    def __init__(self):
        self.conn = get_connection()
        self.sqlite = is_sqlite(self.conn)

    def query(self, sql, params=None):
        sql = adapt_query(sql, self.conn)
        cur = self.conn.cursor()
        try:
            cur.execute(sql, params or [])
            if cur.description:
                columns = [column[0] for column in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
            return []
        except Exception as e:
            print(f"[DB Error] {e} | Query: {sql}")
            raise
        finally:
            cur.close()

    def query_one(self, sql, params=None):
        res = self.query(sql, params)
        return res[0] if res else None

    def execute(self, sql, params=None):
        orig_sql = sql
        sql = adapt_query(sql, self.conn)
        cur = self.conn.cursor()
        try:
            cur.execute(sql, params or [])
            res = None
            if "RETURNING id" in orig_sql:
                if self.sqlite:
                    res = cur.lastrowid
                else:
                    row = cur.fetchone()
                    res = row[0] if row else None
            self.conn.commit()
            return res
        except Exception as e:
            print(f"[DB Error] {e} | Query: {sql}")
            self.conn.rollback()
            raise
        finally:
            cur.close()

    def close(self):
        self.conn.close()
