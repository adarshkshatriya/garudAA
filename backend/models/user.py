from database.schema import get_connection
from psycopg2.extras import RealDictCursor

def get_or_create_user(user_info):
    """
    Fetches a user by google_id. If the user doesn't exist, creates them.
    Returns the user as a dictionary.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    google_id = user_info.get('sub')
    email = user_info.get('email')
    name = user_info.get('name')
    picture = user_info.get('picture')
    
    # Check if user exists
    cur.execute("SELECT * FROM users WHERE google_id = %s", (google_id,))
    user = cur.fetchone()
    
    if not user:
        # Create new user
        cur.execute("""
            INSERT INTO users (google_id, email, name, picture, role)
            VALUES (%s, %s, %s, %s, 'user')
            RETURNING *
        """, (google_id, email, name, picture))
        user = cur.fetchone()
        conn.commit()
        
    cur.close()
    conn.close()
    
    return dict(user) if user else None

def get_user_by_id(user_id):
    """
    Fetches a user by their internal ID.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    return dict(user) if user else None
