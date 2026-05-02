from database.schema import get_connection

def get_or_create_user(user_info):
    """
    Fetches a user by google_id. If the user doesn't exist, creates them.
    Returns the user as a dictionary.
    """
    conn = get_connection()
    c = conn.cursor()
    
    google_id = user_info.get('sub')
    email = user_info.get('email')
    name = user_info.get('name')
    picture = user_info.get('picture')
    
    # Check if user exists
    c.execute("SELECT * FROM users WHERE google_id = ?", (google_id,))
    user = c.fetchone()
    
    if not user:
        # Create new user
        c.execute("""
            INSERT INTO users (google_id, email, name, picture, role)
            VALUES (?, ?, ?, ?, 'user')
        """, (google_id, email, name, picture))
        conn.commit()
        
        c.execute("SELECT * FROM users WHERE google_id = ?", (google_id,))
        user = c.fetchone()
        
    conn.close()
    
    return dict(user) if user else None

def get_user_by_id(user_id):
    """
    Fetches a user by their internal ID.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    
    return dict(user) if user else None
