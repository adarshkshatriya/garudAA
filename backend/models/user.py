from database.db_manager import DBManager

class User:
    @staticmethod
    def get_by_google_id(google_id):
        db = DBManager()
        user = db.query_one("SELECT * FROM users WHERE google_id = %s", [google_id])
        db.close()
        return user

    @staticmethod
    def get_by_id(user_id):
        db = DBManager()
        user = db.query_one("SELECT * FROM users WHERE id = %s", [user_id])
        db.close()
        return user

    @staticmethod
    def create(google_id, email, name, picture=None):
        db = DBManager()
        user_id = db.execute(
            "INSERT INTO users (google_id, email, name, picture) VALUES (%s, %s, %s, %s) RETURNING id",
            (google_id, email, name, picture)
        )
        db.close()
        # Fetch the full user object
        return User.get_by_id(user_id)

def get_or_create_user(google_id, email, name, picture=None):
    user = User.get_by_google_id(google_id)
    if not user:
        user = User.create(google_id, email, name, picture)
    return user
