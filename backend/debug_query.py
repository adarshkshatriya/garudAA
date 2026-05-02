import os
os.environ["DATABASE_URL"] = "sqlite:///synthmon.db"
from database.db_manager import DBManager
from models.models import Monitor

try:
    print("Testing Monitor.get_all(user_id=1)...")
    res = Monitor.get_all(user_id=1)
    print(f"Success! Result: {res}")
except Exception as e:
    import traceback
    traceback.print_exc()
