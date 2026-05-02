import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def create_database():
    try:
        # Connect to default postgres DB
        conn = psycopg2.connect(dbname='postgres', user='postgres', host='localhost')
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Check if DB exists
        cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'synthmon'")
        exists = cur.fetchone()
        
        if not exists:
            cur.execute('CREATE DATABASE synthmon')
            print("Database 'synthmon' created.")
        else:
            print("Database 'synthmon' already exists.")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error creating database: {e}")

if __name__ == "__main__":
    create_database()
